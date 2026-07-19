# Copyright (c) 2026, HM
# ET General Ledger - enhanced General Ledger report
# License: MIT

import frappe
from frappe import _
from frappe.utils import cint, cstr, flt, formatdate, getdate

from erpnext import get_company_currency, get_default_company
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
	get_dimension_with_children,
)
from erpnext.accounts.report.financial_statements import get_cost_centers_with_children
from erpnext.accounts.report.utils import convert_to_presentation_currency, get_currency

DEFAULT_PAGE_LENGTH = 1000
MONTH_KEY_FMT = "%Y-%m"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def execute(filters=None):
	if not filters:
		return [], []

	filters = frappe._dict(filters)
	parse_multi_filters(filters)
	validate_filters(filters)

	columns = get_columns(filters)

	total_count, grand = get_total_count_and_sums(filters)
	gl_entries = get_gl_entries(filters)

	opening = get_opening_totals(filters)
	carried = get_carried_forward(filters, opening)

	data = build_rows(filters, gl_entries, opening, carried)

	message = get_message(filters, total_count, len(gl_entries))
	report_summary = get_report_summary(filters, total_count, grand, opening)

	return columns, data, message, None, report_summary


# ---------------------------------------------------------------------------
# Filters / validation
# ---------------------------------------------------------------------------
def parse_multi_filters(filters):
	for f in ("account", "party", "project", "cost_center"):
		if filters.get(f) and isinstance(filters.get(f), str):
			filters[f] = frappe.parse_json(filters.get(f))


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("{0} is mandatory").format(_("Company")))
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("From Date and To Date are mandatory"))
	if getdate(filters.from_date) > getdate(filters.to_date):
		frappe.throw(_("From Date must be before To Date"))

	if filters.get("account"):
		for account in filters.account:
			if not frappe.db.exists("Account", account):
				frappe.throw(_("Account {0} does not exist").format(account))

	if filters.get("party") and filters.get("party_type"):
		for p in filters.party:
			if not frappe.db.exists(filters.party_type, p):
				frappe.throw(_("Invalid {0}: {1}").format(filters.party_type, p))

	set_account_currency(filters)


def set_account_currency(filters):
	filters["company_currency"] = frappe.get_cached_value(
		"Company", filters.company, "default_currency"
	)
	if not filters.get("presentation_currency"):
		filters["presentation_currency"] = filters.company_currency
	filters["account_currency"] = filters.company_currency


# ---------------------------------------------------------------------------
# SQL conditions (shared by data, count, opening and dashboard queries)
# ---------------------------------------------------------------------------
def get_conditions(filters, mode="range"):
	"""mode: 'range' (period rows), 'opening' (before period), 'all' (no date split)."""
	conditions = []

	if filters.get("account"):
		filters.account = get_accounts_with_children(filters.account)
		if filters.account:
			conditions.append("account in %(account)s")

	# --- NEW: voucher type ---
	if filters.get("voucher_type"):
		conditions.append("voucher_type = %(voucher_type)s")

	# --- NEW: created by ---
	if filters.get("created_by"):
		conditions.append("owner = %(created_by)s")

	# --- NEW: account type / root type ---
	if filters.get("account_type"):
		conditions.append(
			"account in (select name from `tabAccount` "
			"where account_type = %(account_type)s and company = %(company)s)"
		)
	if filters.get("root_type"):
		conditions.append(
			"account in (select name from `tabAccount` "
			"where root_type = %(root_type)s and company = %(company)s)"
		)

	if filters.get("voucher_no"):
		conditions.append("voucher_no = %(voucher_no)s")
	if filters.get("against_voucher_no"):
		conditions.append("against_voucher = %(against_voucher_no)s")

	if filters.get("party_type"):
		conditions.append("party_type = %(party_type)s")
	if filters.get("party"):
		conditions.append("party in %(party)s")

	if filters.get("cost_center"):
		filters.cost_center = get_cost_centers_with_children(filters.cost_center)
		conditions.append("cost_center in %(cost_center)s")
	if filters.get("project"):
		conditions.append("project in %(project)s")

	# Finance book
	if filters.get("finance_book"):
		conditions.append("(finance_book in (%(finance_book)s, '') or finance_book is null)")
	else:
		conditions.append("(finance_book in ('') or finance_book is null)")

	if not filters.get("show_cancelled_entries"):
		conditions.append("is_cancelled = 0")

	# Date window
	if mode == "range":
		conditions.append("posting_date >= %(from_date)s")
		conditions.append("posting_date <= %(to_date)s")
		if not filters.get("show_opening_entries"):
			conditions.append("(is_opening is null or is_opening != 'Yes')")
	elif mode == "opening":
		if filters.get("show_opening_entries"):
			conditions.append("posting_date < %(from_date)s")
		else:
			conditions.append(
				"(posting_date < %(from_date)s or (is_opening = 'Yes' and posting_date <= %(to_date)s))"
			)
	elif mode == "all":
		conditions.append("posting_date <= %(to_date)s")

	# User permissions
	from frappe.desk.reportview import build_match_conditions

	match_conditions = build_match_conditions("GL Entry")
	if match_conditions:
		conditions.append(match_conditions)

	# Accounting dimensions
	accounting_dimensions = get_accounting_dimensions(as_list=False)
	if accounting_dimensions:
		for dimension in accounting_dimensions:
			if not dimension.disabled and dimension.document_type != "Finance Book":
				if filters.get(dimension.fieldname):
					if frappe.get_cached_value("DocType", dimension.document_type, "is_tree"):
						filters[dimension.fieldname] = get_dimension_with_children(
							dimension.document_type, filters.get(dimension.fieldname)
						)
					conditions.append(f"`{dimension.fieldname}` in %({dimension.fieldname})s")

	return " and " + " and ".join(conditions) if conditions else ""


def get_accounts_with_children(accounts):
	if not isinstance(accounts, list):
		accounts = [d.strip() for d in cstr(accounts).strip().split(",") if d]
	if not accounts:
		return accounts

	result = set()
	for account in accounts:
		lft, rgt = frappe.db.get_value("Account", account, ["lft", "rgt"]) or (None, None)
		if lft is None:
			continue
		children = frappe.get_all("Account", filters={"lft": (">=", lft), "rgt": ("<=", rgt)}, pluck="name")
		result.update(children)
	return list(result) or accounts


def get_order_by(filters):
	if cint(filters.get("group_by_month")):
		return "order by posting_date, party, account, creation, name"
	if cint(filters.get("group_by_party")) or cint(filters.get("group_by_party_name")):
		return "order by party_type, party, posting_date, creation, name"
	return "order by posting_date, account, creation, name"


# ---------------------------------------------------------------------------
# Data fetch (paginated - the 1M+ rows fix)
# ---------------------------------------------------------------------------
def get_page_window(filters):
	page_length = cint(filters.get("page_length")) or DEFAULT_PAGE_LENGTH
	page_no = max(cint(filters.get("page_no")) or 1, 1)
	offset = (page_no - 1) * page_length
	return page_length, page_no, offset


def get_gl_entries(filters):
	page_length, _page_no, offset = get_page_window(filters)
	currency_map = get_currency(filters)

	select_remarks = ""
	if filters.get("show_remarks"):
		remarks_length = frappe.db.get_single_value("Accounts Settings", "general_ledger_remarks_length")
		if remarks_length:
			select_remarks = f", substr(remarks, 1, {cint(remarks_length)}) as remarks"
		else:
			select_remarks = ", remarks"

	dimension_fields = ""
	accounting_dimensions = get_accounting_dimensions()
	if accounting_dimensions:
		dimension_fields = ", " + ", ".join(f"`{d}`" for d in accounting_dimensions)

	gl_entries = frappe.db.sql(
		f"""
		select
			name as gl_entry, posting_date, account, party_type, party,
			voucher_type, voucher_subtype, voucher_no, cost_center, project,
			against_voucher_type, against_voucher, account_currency,
			against, is_opening, creation, owner,
			debit, credit, debit_in_account_currency, credit_in_account_currency
			{dimension_fields}
			{select_remarks}
		from `tabGL Entry`
		where company = %(company)s {get_conditions(filters, "range")}
		{get_order_by(filters)}
		limit {page_length} offset {offset}
		""",
		filters,
		as_dict=1,
	)

	# Party names
	if gl_entries:
		party_name_map = get_party_name_map({(g.party_type, g.party) for g in gl_entries if g.party})
		for gle in gl_entries:
			if gle.party_type and gle.party:
				gle.party_name = party_name_map.get((gle.party_type, gle.party)) or gle.party

	if filters.get("presentation_currency") and filters.presentation_currency != filters.company_currency:
		gl_entries = convert_to_presentation_currency(gl_entries, currency_map, filters)

	return gl_entries


def get_party_name_map(party_keys):
	"""Fetch names only for the parties on this page (fast even with huge masters)."""
	out = {}
	by_type = {}
	for ptype, party in party_keys:
		by_type.setdefault(ptype, set()).add(party)

	name_field = {"Customer": "customer_name", "Supplier": "supplier_name", "Employee": "employee_name"}
	for ptype, parties in by_type.items():
		field = name_field.get(ptype)
		if not field or not frappe.db.exists("DocType", ptype):
			continue
		for d in frappe.get_all(ptype, filters={"name": ("in", list(parties))}, fields=["name", field]):
			out[(ptype, d.name)] = d.get(field)
	return out


def get_total_count_and_sums(filters):
	row = frappe.db.sql(
		f"""
		select count(*) as cnt,
			ifnull(sum(debit), 0) as debit,
			ifnull(sum(credit), 0) as credit
		from `tabGL Entry`
		where company = %(company)s {get_conditions(filters, "range")}
		""",
		filters,
		as_dict=1,
	)[0]
	return cint(row.cnt), row


def get_opening_totals(filters):
	row = frappe.db.sql(
		f"""
		select ifnull(sum(debit), 0) as debit, ifnull(sum(credit), 0) as credit
		from `tabGL Entry`
		where company = %(company)s {get_conditions(filters, "opening")}
		""",
		filters,
		as_dict=1,
	)[0]
	return row


def get_carried_forward(filters, opening):
	"""Balance carried from previous pages so the running balance stays correct."""
	_page_length, page_no, offset = get_page_window(filters)
	balance = flt(opening.debit) - flt(opening.credit)
	if page_no <= 1:
		return balance

	prev = frappe.db.sql(
		f"""
		select ifnull(sum(t.debit), 0) as debit, ifnull(sum(t.credit), 0) as credit
		from (
			select debit, credit
			from `tabGL Entry`
			where company = %(company)s {get_conditions(filters, "range")}
			{get_order_by(filters)}
			limit {offset}
		) t
		""",
		filters,
		as_dict=1,
	)[0]
	return balance + flt(prev.debit) - flt(prev.credit)


# ---------------------------------------------------------------------------
# Row building with collapsible grouping (month / party / party name)
# ---------------------------------------------------------------------------
def build_rows(filters, gl_entries, opening, carried):
	data = []
	_page_length, page_no, _offset = get_page_window(filters)

	group_levels = []
	if cint(filters.get("group_by_month")):
		group_levels.append("month")
	if cint(filters.get("group_by_party")):
		group_levels.append("party")
	if cint(filters.get("group_by_party_name")):
		group_levels.append("party_name")

	balance = carried

	# Opening row (page 1 only)
	if page_no == 1:
		data.append(
			frappe._dict(
				account=_("'Opening'"),
				debit=flt(opening.debit),
				credit=flt(opening.credit),
				balance=flt(opening.debit) - flt(opening.credit),
				is_group_header=1,
				is_summary_row=1,
				indent=0,
			)
		)

	entry_indent = len(group_levels)

	def make_row(gle):
		nonlocal balance
		balance += flt(gle.debit) - flt(gle.credit)
		row = frappe._dict(gle)
		row.balance = balance
		row.indent = entry_indent
		row.account_currency = filters.account_currency
		row.presentation_currency = filters.presentation_currency
		return row

	if not group_levels:
		for gle in gl_entries:
			data.append(make_row(gle))
	else:
		tree = build_group_tree(gl_entries, group_levels)
		emit_groups(data, tree, group_levels, 0, make_row)

	# Grand total for this page + closing
	page_debit = sum(flt(g.debit) for g in gl_entries)
	page_credit = sum(flt(g.credit) for g in gl_entries)
	data.append(
		frappe._dict(
			account=_("'Total (this page)'"),
			debit=page_debit,
			credit=page_credit,
			is_group_header=1,
			is_summary_row=1,
			indent=0,
		)
	)
	data.append(
		frappe._dict(
			account=_("'Closing (running)'"),
			balance=balance,
			is_group_header=1,
			is_summary_row=1,
			indent=0,
		)
	)
	return data


def group_key(gle, level):
	if level == "month":
		d = getdate(gle.posting_date)
		return (d.strftime(MONTH_KEY_FMT), formatdate(gle.posting_date, "MMMM yyyy"))
	if level == "party":
		return (gle.party or "zzz", gle.party or _("No Party"))
	if level == "party_name":
		label = gle.get("party_name") or gle.party or _("No Party")
		return (label, label)
	return ("", "")


def build_group_tree(gl_entries, group_levels):
	"""Nested ordered dict: key -> {label, entries, children}."""
	tree = {}
	for gle in gl_entries:
		node = tree
		for i, level in enumerate(group_levels):
			key, label = group_key(gle, level)
			node = node.setdefault(key, {"label": label, "children": {}, "entries": []})
			if i == len(group_levels) - 1:
				node["entries"].append(gle)
			else:
				node = node["children"]
	return tree


def emit_groups(data, tree, group_levels, depth, make_row):
	level_debit = level_credit = 0.0
	for _key, node in tree.items():
		header_idx = len(data)
		data.append(
			frappe._dict(
				account=node["label"],
				is_group_header=1,
				indent=depth,
				debit=0.0,
				credit=0.0,
			)
		)
		sub_debit = sub_credit = 0.0

		if node["children"]:
			child_debit, child_credit = emit_groups(
				data, node["children"], group_levels, depth + 1, make_row
			)
			sub_debit += child_debit
			sub_credit += child_credit

		for gle in node["entries"]:
			row = make_row(gle)
			data.append(row)
			sub_debit += flt(gle.debit)
			sub_credit += flt(gle.credit)

		data[header_idx].debit = sub_debit
		data[header_idx].credit = sub_credit
		level_debit += sub_debit
		level_credit += sub_credit

	return level_debit, level_credit


# ---------------------------------------------------------------------------
# Message + summary strip
# ---------------------------------------------------------------------------
def get_message(filters, total_count, page_rows):
	page_length, page_no, offset = get_page_window(filters)
	start = offset + 1 if page_rows else 0
	end = offset + page_rows
	total_pages = max((total_count + page_length - 1) // page_length, 1)
	return _(
		"Showing rows {0}–{1} of {2} (page {3} of {4}). "
		"Use the Page No filter or the Prev / Next Page buttons to navigate large ledgers."
	).format(
		frappe.format(start), frappe.format(end), frappe.format(total_count), page_no, total_pages
	)


def get_report_summary(filters, total_count, grand, opening):
	currency = filters.presentation_currency
	net = flt(grand.debit) - flt(grand.credit)
	closing = flt(opening.debit) - flt(opening.credit) + net
	return [
		{"value": total_count, "label": _("GL Entries"), "datatype": "Int", "indicator": "Blue"},
		{"value": grand.debit, "label": _("Total Debit"), "datatype": "Currency", "currency": currency},
		{"value": grand.credit, "label": _("Total Credit"), "datatype": "Currency", "currency": currency},
		{
			"value": closing,
			"label": _("Closing Balance"),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Green" if closing >= 0 else "Red",
		},
	]


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------
def get_columns(filters):
	currency = filters.get("presentation_currency") or get_company_currency(
		filters.get("company") or get_default_company()
	)
	filters["presentation_currency"] = currency

	columns = [
		{
			"label": _("GL Entry"),
			"fieldname": "gl_entry",
			"fieldtype": "Link",
			"options": "GL Entry",
			"hidden": 1,
		},
		{"label": _("Posting Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{
			"label": _("Account"),
			"fieldname": "account",
			"fieldtype": "Link",
			"options": "Account",
			"width": 220,
		},
		{
			"label": _("Debit ({0})").format(currency),
			"fieldname": "debit",
			"fieldtype": "Currency",
			"options": "presentation_currency",
			"width": 130,
		},
		{
			"label": _("Credit ({0})").format(currency),
			"fieldname": "credit",
			"fieldtype": "Currency",
			"options": "presentation_currency",
			"width": 130,
		},
		{
			"label": _("Balance ({0})").format(currency),
			"fieldname": "balance",
			"fieldtype": "Currency",
			"options": "presentation_currency",
			"width": 130,
		},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "width": 120},
		{
			"label": _("Voucher No"),
			"fieldname": "voucher_no",
			"fieldtype": "Dynamic Link",
			"options": "voucher_type",
			"width": 200,
		},
		{"label": _("Party Type"), "fieldname": "party_type", "width": 90},
		{"label": _("Party"), "fieldname": "party", "width": 120},
		{"label": _("Party Name"), "fieldname": "party_name", "fieldtype": "Data", "width": 150},
		{"label": _("Against Account"), "fieldname": "against", "width": 120},
		{
			"label": _("Against Voucher"),
			"fieldname": "against_voucher",
			"fieldtype": "Dynamic Link",
			"options": "against_voucher_type",
			"width": 120,
		},
		{
			"label": _("Created By"),
			"fieldname": "owner",
			"fieldtype": "Link",
			"options": "User",
			"width": 130,
		},
		{
			"label": _("Cost Center"),
			"fieldname": "cost_center",
			"fieldtype": "Link",
			"options": "Cost Center",
			"width": 100,
		},
		{
			"label": _("Project"),
			"fieldname": "project",
			"fieldtype": "Link",
			"options": "Project",
			"width": 100,
		},
	]

	for dim in get_accounting_dimensions(as_list=False):
		if not dim.disabled:
			columns.append(
				{
					"label": _(dim.label),
					"fieldname": dim.fieldname,
					"options": dim.document_type,
					"width": 100,
				}
			)

	if filters.get("show_remarks"):
		columns.append({"label": _("Remarks"), "fieldname": "remarks", "width": 400})

	return columns


# ---------------------------------------------------------------------------
# Whitelisted: voucher details popup (eye icon)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_voucher_details(voucher_type, voucher_no):
	frappe.has_permission("GL Entry", "read", throw=True)

	gl_rows = frappe.db.sql(
		"""
		select posting_date, account, party_type, party, cost_center, project,
			against, debit, credit, remarks, is_cancelled
		from `tabGL Entry`
		where voucher_type = %s and voucher_no = %s
		order by posting_date, creation
		""",
		(voucher_type, voucher_no),
		as_dict=1,
	)

	doc_info = None
	if frappe.db.exists(voucher_type, voucher_no):
		fields = ["owner", "creation", "modified", "modified_by", "docstatus"]
		doc_info = frappe.db.get_value(voucher_type, voucher_no, fields, as_dict=True)
		if doc_info:
			doc_info.owner_name = frappe.utils.get_fullname(doc_info.owner)
			doc_info.docstatus_label = {0: _("Draft"), 1: _("Submitted"), 2: _("Cancelled")}.get(
				cint(doc_info.docstatus)
			)

	return {
		"gl_entries": gl_rows,
		"doc_info": doc_info,
		"total_debit": sum(flt(r.debit) for r in gl_rows),
		"total_credit": sum(flt(r.credit) for r in gl_rows),
	}


# ---------------------------------------------------------------------------
# Whitelisted: dashboard aggregates (fast SQL group-bys, no row streaming)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_dashboard_data(filters):
	frappe.has_permission("GL Entry", "read", throw=True)

	filters = frappe._dict(frappe.parse_json(filters))
	parse_multi_filters(filters)
	validate_filters(filters)
	conditions = get_conditions(filters, "range")

	totals = frappe.db.sql(
		f"""
		select count(*) as cnt, ifnull(sum(debit), 0) as debit, ifnull(sum(credit), 0) as credit,
			count(distinct account) as accounts, count(distinct voucher_no) as vouchers
		from `tabGL Entry` where company = %(company)s {conditions}
		""",
		filters,
		as_dict=1,
	)[0]

	by_month = frappe.db.sql(
		f"""
		select date_format(posting_date, '%%Y-%%m') as mkey,
			date_format(posting_date, '%%b %%Y') as label,
			ifnull(sum(debit), 0) as debit, ifnull(sum(credit), 0) as credit
		from `tabGL Entry` where company = %(company)s {conditions}
		group by mkey, label order by mkey
		""",
		filters,
		as_dict=1,
	)

	by_voucher_type = frappe.db.sql(
		f"""
		select voucher_type as label,
			ifnull(sum(debit), 0) + ifnull(sum(credit), 0) as amount, count(*) as cnt
		from `tabGL Entry` where company = %(company)s {conditions}
		group by voucher_type order by amount desc limit 8
		""",
		filters,
		as_dict=1,
	)

	top_accounts = frappe.db.sql(
		f"""
		select account as label,
			ifnull(sum(debit), 0) as debit, ifnull(sum(credit), 0) as credit
		from `tabGL Entry` where company = %(company)s {conditions}
		group by account
		order by (ifnull(sum(debit), 0) + ifnull(sum(credit), 0)) desc limit 10
		""",
		filters,
		as_dict=1,
	)

	top_parties = frappe.db.sql(
		f"""
		select party_type, party as label,
			ifnull(sum(debit), 0) as debit, ifnull(sum(credit), 0) as credit
		from `tabGL Entry`
		where company = %(company)s and ifnull(party, '') != '' {conditions}
		group by party_type, party
		order by (ifnull(sum(debit), 0) + ifnull(sum(credit), 0)) desc limit 10
		""",
		filters,
		as_dict=1,
	)

	return {
		"currency": filters.presentation_currency,
		"totals": totals,
		"by_month": by_month,
		"by_voucher_type": by_voucher_type,
		"top_accounts": top_accounts,
		"top_parties": top_parties,
	}
