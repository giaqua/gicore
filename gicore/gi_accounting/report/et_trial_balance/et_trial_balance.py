# Copyright (c) 2026, HM and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.query_builder.functions import Sum
from frappe.utils import add_days, cint, cstr, flt, formatdate, getdate

import erpnext
from erpnext.accounts.doctype.accounting_dimension.accounting_dimension import (
	get_accounting_dimensions,
	get_dimension_with_children,
)
from erpnext.accounts.report.financial_statements import (
	filter_accounts,
	filter_out_zero_value_rows,
	get_cost_centers_with_children,
)
from erpnext.accounts.report.utils import convert_to_presentation_currency, get_currency
from erpnext.accounts.utils import get_zero_cutoff

value_fields = (
	"opening_debit",
	"opening_credit",
	"debit",
	"credit",
	"closing_debit",
	"closing_credit",
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)
	data = get_data(filters)
	columns = get_columns()
	return columns, data


def validate_filters(filters):
	if not filters.fiscal_year:
		frappe.throw(_("Fiscal Year {0} is required").format(filters.fiscal_year))

	fiscal_year = frappe.get_cached_value(
		"Fiscal Year", filters.fiscal_year, ["year_start_date", "year_end_date"], as_dict=True
	)
	if not fiscal_year:
		frappe.throw(_("Fiscal Year {0} does not exist").format(filters.fiscal_year))
	else:
		filters.year_start_date = getdate(fiscal_year.year_start_date)
		filters.year_end_date = getdate(fiscal_year.year_end_date)

	if not filters.from_date:
		filters.from_date = filters.year_start_date

	if not filters.to_date:
		filters.to_date = filters.year_end_date

	filters.from_date = getdate(filters.from_date)
	filters.to_date = getdate(filters.to_date)

	if filters.from_date > filters.to_date:
		frappe.throw(_("From Date cannot be greater than To Date"))

	if (filters.from_date < filters.year_start_date) or (filters.from_date > filters.year_end_date):
		frappe.msgprint(
			_("From Date should be within the Fiscal Year. Assuming From Date = {0}").format(
				formatdate(filters.year_start_date)
			)
		)
		filters.from_date = filters.year_start_date

	if (filters.to_date < filters.year_start_date) or (filters.to_date > filters.year_end_date):
		frappe.msgprint(
			_("To Date should be within the Fiscal Year. Assuming To Date = {0}").format(
				formatdate(filters.year_end_date)
			)
		)
		filters.to_date = filters.year_end_date

	if filters.get("level") not in (None, ""):
		filters.level = cint(filters.level)


def get_data(filters):
	# root_type is safe to filter at the account-tree level: an entire
	# subtree in a standard CoA shares one root_type, so trimming it here
	# doesn't orphan any branch.
	conditions = ""
	values = [filters.company]

	if filters.get("root_type"):
		conditions += " and root_type = %s"
		values.append(filters.root_type)

	accounts = frappe.db.sql(
		f"""select name, account_number, parent_account, account_name,
			root_type, report_type, account_type, is_group, lft, rgt
		from `tabAccount`
		where company=%s {conditions}
		order by lft""",
		tuple(values),
		as_dict=True,
	)
	company_currency = filters.presentation_currency or erpnext.get_company_currency(filters.company)

	ignore_is_opening = frappe.db.get_single_value(
		"Accounts Settings", "ignore_is_opening_check_for_reporting"
	)

	if not accounts:
		return None

	accounts, accounts_by_name, parent_children_map = filter_accounts(accounts)

	gl_entries_by_account = {}

	opening_balances = get_opening_balances(filters, ignore_is_opening)

	set_gl_entries_by_account(
		filters.company,
		filters.from_date,
		filters.to_date,
		filters,
		gl_entries_by_account,
	)

	calculate_values(
		accounts,
		gl_entries_by_account,
		opening_balances,
		filters.get("show_net_values"),
		ignore_is_opening=ignore_is_opening,
	)
	accumulate_values_into_parents(accounts, accounts_by_name)

	data = prepare_data(accounts, filters, parent_children_map, company_currency)
	data = filter_out_zero_value_rows(
		data, parent_children_map, show_zero_values=filters.get("show_zero_values")
	)

	return data


# ----------------------------------------------------------------------
# Opening balances (unchanged logic from core Trial Balance)
# ----------------------------------------------------------------------


def get_opening_balances(filters, ignore_is_opening):
	balance_sheet_opening = get_rootwise_opening_balances(filters, "Balance Sheet", ignore_is_opening)
	pl_opening = get_rootwise_opening_balances(filters, "Profit and Loss", ignore_is_opening)

	balance_sheet_opening.update(pl_opening)
	return balance_sheet_opening


def get_rootwise_opening_balances(filters, report_type, ignore_is_opening):
	gle = []

	last_period_closing_voucher = ""
	ignore_closing_balances = frappe.db.get_single_value(
		"Accounts Settings", "ignore_account_closing_balance"
	)

	if not ignore_closing_balances:
		last_period_closing_voucher = frappe.db.get_all(
			"Period Closing Voucher",
			filters={"docstatus": 1, "company": filters.company, "period_end_date": ("<", filters.from_date)},
			fields=["period_end_date", "name"],
			order_by="period_end_date desc",
			limit=1,
		)

	accounting_dimensions = get_accounting_dimensions(as_list=False)

	if last_period_closing_voucher:
		gle = get_opening_balance(
			"Account Closing Balance",
			filters,
			report_type,
			accounting_dimensions,
			period_closing_voucher=last_period_closing_voucher[0].name,
			ignore_is_opening=ignore_is_opening,
		)

		if getdate(last_period_closing_voucher[0].period_end_date) < getdate(add_days(filters.from_date, -1)):
			start_date = add_days(last_period_closing_voucher[0].period_end_date, 1)
			gle += get_opening_balance(
				"GL Entry",
				filters,
				report_type,
				accounting_dimensions,
				start_date=start_date,
				ignore_is_opening=ignore_is_opening,
			)
	else:
		gle = get_opening_balance(
			"GL Entry", filters, report_type, accounting_dimensions, ignore_is_opening=ignore_is_opening
		)

	opening = frappe._dict()
	for d in gle:
		opening.setdefault(
			d.account,
			{
				"account": d.account,
				"opening_debit": 0.0,
				"opening_credit": 0.0,
			},
		)
		opening[d.account]["opening_debit"] += flt(d.debit)
		opening[d.account]["opening_credit"] += flt(d.credit)

	return opening


def get_opening_balance(
	doctype,
	filters,
	report_type,
	accounting_dimensions,
	period_closing_voucher=None,
	start_date=None,
	ignore_is_opening=0,
):
	closing_balance = frappe.qb.DocType(doctype)
	accounts = frappe.db.get_all("Account", filters={"report_type": report_type}, pluck="name")

	opening_balance = (
		frappe.qb.from_(closing_balance)
		.select(
			closing_balance.account,
			closing_balance.account_currency,
			Sum(closing_balance.debit).as_("debit"),
			Sum(closing_balance.credit).as_("credit"),
			Sum(closing_balance.debit_in_account_currency).as_("debit_in_account_currency"),
			Sum(closing_balance.credit_in_account_currency).as_("credit_in_account_currency"),
		)
		.where((closing_balance.company == filters.company) & (closing_balance.account.isin(accounts)))
		.groupby(closing_balance.account)
	)

	if period_closing_voucher:
		opening_balance = opening_balance.where(
			closing_balance.period_closing_voucher == period_closing_voucher
		)
	else:
		if start_date:
			opening_balance = opening_balance.where(
				(closing_balance.posting_date >= start_date)
				& (closing_balance.posting_date < filters.from_date)
			)
			if not ignore_is_opening:
				opening_balance = opening_balance.where(closing_balance.is_opening == "No")
		else:
			if not ignore_is_opening:
				opening_balance = opening_balance.where(
					(closing_balance.posting_date < filters.from_date) | (closing_balance.is_opening == "Yes")
				)
			else:
				opening_balance = opening_balance.where(closing_balance.posting_date < filters.from_date)

	if doctype == "GL Entry":
		opening_balance = opening_balance.where(closing_balance.is_cancelled == 0)

	if (
		not filters.show_unclosed_fy_pl_balances
		and report_type == "Profit and Loss"
		and doctype == "GL Entry"
	):
		opening_balance = opening_balance.where(closing_balance.posting_date >= filters.year_start_date)

	if not flt(filters.with_period_closing_entry_for_opening):
		if doctype == "Account Closing Balance":
			opening_balance = opening_balance.where(closing_balance.is_period_closing_voucher_entry == 0)
		else:
			opening_balance = opening_balance.where(closing_balance.voucher_type != "Period Closing Voucher")

	if filters.cost_center:
		opening_balance = opening_balance.where(
			closing_balance.cost_center.isin(get_cost_centers_with_children(filters.get("cost_center")))
		)

	if filters.project:
		opening_balance = opening_balance.where(closing_balance.project.isin(filters.project))

	# Party filter on opening balances only applies if the field exists on
	# this doctype in your version. Guarded via meta check so it never
	# throws on older/newer schemas.
	if filters.get("party_type") and has_field(doctype, "party_type"):
		opening_balance = opening_balance.where(closing_balance.party_type == filters.party_type)

	if filters.get("party") and has_field(doctype, "party"):
		party_list = filters.party if isinstance(filters.party, list) else [filters.party]
		opening_balance = opening_balance.where(closing_balance.party.isin(party_list))

	if frappe.db.count("Finance Book"):
		if filters.get("include_default_book_entries"):
			company_fb = frappe.get_cached_value("Company", filters.company, "default_finance_book")

			if filters.finance_book and company_fb and cstr(filters.finance_book) != cstr(company_fb):
				frappe.throw(
					_("To use a different finance book, please uncheck 'Include Default FB Entries'")
				)

			opening_balance = opening_balance.where(
				(closing_balance.finance_book.isin([cstr(filters.finance_book), cstr(company_fb), ""]))
				| (closing_balance.finance_book.isnull())
			)
		else:
			opening_balance = opening_balance.where(
				(closing_balance.finance_book.isin([cstr(filters.finance_book), ""]))
				| (closing_balance.finance_book.isnull())
			)

	if accounting_dimensions:
		for dimension in accounting_dimensions:
			if filters.get(dimension.fieldname):
				if frappe.get_cached_value("DocType", dimension.document_type, "is_tree"):
					filters[dimension.fieldname] = get_dimension_with_children(
						dimension.document_type, filters.get(dimension.fieldname)
					)
					opening_balance = opening_balance.where(
						closing_balance[dimension.fieldname].isin(filters[dimension.fieldname])
					)
				else:
					opening_balance = opening_balance.where(
						closing_balance[dimension.fieldname].isin(filters[dimension.fieldname])
					)

	gle = opening_balance.run(as_dict=1)

	if filters and filters.get("presentation_currency"):
		convert_to_presentation_currency(gle, get_currency(filters))

	return gle


def has_field(doctype, fieldname):
	try:
		return frappe.get_meta(doctype).has_field(fieldname)
	except Exception:
		return False


# ----------------------------------------------------------------------
# Period movement — custom fetch so we can add party/voucher filters
# (core's set_gl_entries_by_account doesn't accept these)
# ----------------------------------------------------------------------


def set_gl_entries_by_account(company, from_date, to_date, filters, gl_entries_by_account):
	gle = frappe.qb.DocType("GL Entry")

	query = (
		frappe.qb.from_(gle)
		.select(
			gle.account,
			gle.posting_date,
			gle.debit,
			gle.credit,
			gle.is_opening,
			gle.fiscal_year,
			gle.voucher_type,
			gle.voucher_no,
			gle.party_type,
			gle.party,
			gle.cost_center,
			gle.project,
		)
		.where(
			(gle.company == company)
			& (gle.posting_date >= from_date)
			& (gle.posting_date <= to_date)
			& (gle.is_cancelled == 0)
		)
	)

	if not cint(filters.get("with_period_closing_entry_for_current_period")):
		query = query.where(gle.voucher_type != "Period Closing Voucher")

	if filters.get("cost_center"):
		query = query.where(
			gle.cost_center.isin(get_cost_centers_with_children(filters.get("cost_center")))
		)

	if filters.get("project"):
		project_list = filters.project if isinstance(filters.project, list) else [filters.project]
		query = query.where(gle.project.isin(project_list))

	if filters.get("party_type"):
		query = query.where(gle.party_type == filters.party_type)

	if filters.get("party"):
		party_list = filters.party if isinstance(filters.party, list) else [filters.party]
		query = query.where(gle.party.isin(party_list))

	if filters.get("voucher_type"):
		query = query.where(gle.voucher_type == filters.voucher_type)

	if filters.get("voucher_no"):
		query = query.where(gle.voucher_no == filters.voucher_no)

	if filters.get("finance_book"):
		query = query.where(
			(gle.finance_book == filters.finance_book) | (gle.finance_book.isnull()) | (gle.finance_book == "")
		)

	gl_entries = query.run(as_dict=True)

	if filters.get("presentation_currency"):
		convert_to_presentation_currency(gl_entries, get_currency(filters))

	for entry in gl_entries:
		gl_entries_by_account.setdefault(entry.account, []).append(entry)


# ----------------------------------------------------------------------
# Aggregation (unchanged from core)
# ----------------------------------------------------------------------


def calculate_values(accounts, gl_entries_by_account, opening_balances, show_net_values, ignore_is_opening=0):
	init = {
		"opening_debit": 0.0,
		"opening_credit": 0.0,
		"debit": 0.0,
		"credit": 0.0,
		"closing_debit": 0.0,
		"closing_credit": 0.0,
	}

	for d in accounts:
		d.update(init.copy())

		d["opening_debit"] = opening_balances.get(d.name, {}).get("opening_debit", 0)
		d["opening_credit"] = opening_balances.get(d.name, {}).get("opening_credit", 0)

		for entry in gl_entries_by_account.get(d.name, []):
			if cstr(entry.is_opening) != "Yes" or ignore_is_opening:
				d["debit"] += flt(entry.debit)
				d["credit"] += flt(entry.credit)

		d["closing_debit"] = d["opening_debit"] + d["debit"]
		d["closing_credit"] = d["opening_credit"] + d["credit"]

		if show_net_values:
			prepare_opening_closing(d)


def calculate_total_row(accounts, company_currency):
	total_row = {
		"account": "'" + _("Total") + "'",
		"account_name": "'" + _("Total") + "'",
		"warn_if_negative": True,
		"opening_debit": 0.0,
		"opening_credit": 0.0,
		"debit": 0.0,
		"credit": 0.0,
		"closing_debit": 0.0,
		"closing_credit": 0.0,
		"parent_account": None,
		"indent": 0,
		"has_value": True,
		"currency": company_currency,
	}

	for d in accounts:
		if not d.parent_account:
			for field in value_fields:
				total_row[field] += d[field]

	return total_row


def accumulate_values_into_parents(accounts, accounts_by_name):
	for d in reversed(accounts):
		if d.parent_account:
			for key in value_fields:
				accounts_by_name[d.parent_account][key] += d[key]


# ----------------------------------------------------------------------
# Display-stage filtering: level, account_type, is_group.
# Done AFTER aggregation so parent totals stay correct even when the
# row itself is trimmed from the output.
# ----------------------------------------------------------------------


def prepare_data(accounts, filters, parent_children_map, company_currency):
	data = []

	only_ledger_accounts = cint(filters.get("only_ledger_accounts"))
	account_type = filters.get("account_type")
	level = filters.get("level")

	for d in accounts:
		if parent_children_map.get(d.account) and filters.get("show_net_values"):
			prepare_opening_closing(d)

		# Level: keep tree intact, just don't emit rows deeper than requested
		if level not in (None, "") and d.indent > level:
			continue

		# is_group / account_type: only leaf (postable) accounts qualify.
		# Group accounts never carry account_type, so this also covers
		# "only_ledger_accounts" naturally.
		if only_ledger_accounts and d.is_group:
			continue

		if account_type and (d.is_group or d.account_type != account_type):
			continue

		has_value = False
		row = {
			"account": d.name,
			"parent_account": d.parent_account,
			"indent": d.indent,
			"is_group": d.is_group,
			"account_type": d.account_type,
			"root_type": d.root_type,
			"from_date": filters.from_date,
			"to_date": filters.to_date,
			"currency": company_currency,
			"account_name": (
				f"{d.account_number} - {d.account_name}" if d.account_number else d.account_name
			),
		}

		# When we've dropped ancestor group rows (ledger-only / account_type
		# modes), re-root the remaining rows so the tree renderer doesn't
		# look for a parent that isn't in the result set.
		if (only_ledger_accounts or account_type) and row["parent_account"] not in [a["account"] for a in data]:
			row["parent_account"] = None
			row["indent"] = 0

		for key in value_fields:
			row[key] = flt(d.get(key, 0.0))
			if abs(row[key]) >= get_zero_cutoff(company_currency):
				has_value = True

		row["has_value"] = has_value
		data.append(row)

	total_row = calculate_total_row(accounts, company_currency)
	data.extend([{}, total_row])

	return data


def get_columns():
	return [
		{
			"fieldname": "account",
			"label": _("Account"),
			"fieldtype": "Link",
			"options": "Account",
			"width": 300,
		},
		{
			"fieldname": "currency",
			"label": _("Currency"),
			"fieldtype": "Link",
			"options": "Currency",
			"hidden": 1,
		},
		{
			"fieldname": "opening_debit",
			"label": _("Opening (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "opening_credit",
			"label": _("Opening (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "debit",
			"label": _("Debit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "credit",
			"label": _("Credit"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_debit",
			"label": _("Closing (Dr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
		{
			"fieldname": "closing_credit",
			"label": _("Closing (Cr)"),
			"fieldtype": "Currency",
			"options": "currency",
			"width": 120,
		},
	]


def prepare_opening_closing(row):
	dr_or_cr = "debit" if row["root_type"] in ["Asset", "Equity", "Expense"] else "credit"
	reverse_dr_or_cr = "credit" if dr_or_cr == "debit" else "debit"

	for col_type in ["opening", "closing"]:
		valid_col = col_type + "_" + dr_or_cr
		reverse_col = col_type + "_" + reverse_dr_or_cr
		row[valid_col] -= row[reverse_col]
		if row[valid_col] < 0:
			row[reverse_col] = abs(row[valid_col])
			row[valid_col] = 0.0
		else:
			row[reverse_col] = 0.0


# ----------------------------------------------------------------------
# Eye-icon popup: whitelisted endpoint returning raw GL transactions
# for a single account, respecting the same filters as the report.
# ----------------------------------------------------------------------


@frappe.whitelist()
def get_account_transactions(
	account,
	company,
	from_date,
	to_date,
	party_type=None,
	party=None,
	cost_center=None,
	project=None,
	voucher_type=None,
	voucher_no=None,
):
	filters = {
		"account": account,
		"company": company,
		"posting_date": ["between", [from_date, to_date]],
		"is_cancelled": 0,
	}
	if party_type:
		filters["party_type"] = party_type
	if party:
		filters["party"] = party
	if cost_center and len(cost_center) > 0 and cost_center[0] != "[":
		filters["cost_center"] = cost_center
	if project and len(project) > 0 and project[0] != "[":
		filters["project"] = project

	if voucher_type:
		filters["voucher_type"] = voucher_type
	if voucher_no:
		filters["voucher_no"] = voucher_no

	account_transactions = frappe.get_all(
		"GL Entry",
		filters=filters,
		fields=[
			"name",
			"posting_date",
			"voucher_type",
			"voucher_no",
			"against",
			"party_type",
			"party",
			"debit",
			"credit",
			"cost_center",
			"project",
			"remarks",
		],
		order_by="posting_date asc, creation asc",
	)

	return account_transactions


# ----------------------------------------------------------------------
# Print designs — three layouts, bilingual EN/AR, HM brand colors.
# Rendered server-side as plain HTML (no Print Format doctype needed
# since this is a script report, not a submittable document).
# ----------------------------------------------------------------------

import json

from frappe.utils.pdf import get_pdf

HM_BLUE = "#010BCE"
HM_RED = "#D50000"

LABELS = {
	"en": {
		"title": "Trial Balance",
		"account": "Account",
		"opening_dr": "Opening (Dr)",
		"opening_cr": "Opening (Cr)",
		"debit": "Debit",
		"credit": "Credit",
		"closing_dr": "Closing (Dr)",
		"closing_cr": "Closing (Cr)",
		"total": "Total",
		"period": "Period",
		"company": "Company",
		"from": "From",
		"to": "To",
		"assets": "Assets",
		"liabilities": "Liabilities",
		"equity": "Equity",
		"income": "Income",
		"expense": "Expense",
		"net_income": "Net Income",
		"date": "Date",
		"voucher": "Voucher No",
		"voucher_type": "Voucher Type",
		"party": "Party",
	},
	"ar": {
		"title": "ميزان المراجعة",
		"account": "الحساب",
		"opening_dr": "افتتاحي (مدين)",
		"opening_cr": "افتتاحي (دائن)",
		"debit": "مدين",
		"credit": "دائن",
		"closing_dr": "ختامي (مدين)",
		"closing_cr": "ختامي (دائن)",
		"total": "الإجمالي",
		"period": "الفترة",
		"company": "الشركة",
		"from": "من",
		"to": "إلى",
		"assets": "الأصول",
		"liabilities": "الالتزامات",
		"equity": "حقوق الملكية",
		"income": "الإيرادات",
		"expense": "المصروفات",
		"net_income": "صافي الدخل",
		"date": "التاريخ",
		"voucher": "رقم المستند",
		"voucher_type": "نوع المستند",
		"party": "الطرف",
	},
}

ROOT_TYPE_LABEL_KEY = {
	"Asset": "assets",
	"Liability": "liabilities",
	"Equity": "equity",
	"Income": "income",
	"Expense": "expense",
}


def _base_css(is_ar):
	align = "right" if is_ar else "left"
	opp_align = "left" if is_ar else "right"
	return f"""
		body {{
			font-family: {"'Tahoma','Arial',sans-serif" if is_ar else "'Segoe UI','Arial',sans-serif"};
			color: #1a1a1a;
			margin: 24px;
			font-size: 12px;
		}}
		.et-header {{
			border-bottom: 3px solid {HM_BLUE};
			padding-bottom: 10px;
			margin-bottom: 16px;
			display: flex;
			justify-content: space-between;
			align-items: flex-start;
		}}
		.et-header h1 {{
			color: {HM_BLUE};
			font-size: 20px;
			margin: 0 0 4px 0;
		}}
		.et-header .meta {{
			font-size: 11px;
			color: #444;
			text-align: {opp_align};
		}}
		table.et-table {{
			width: 100%;
			border-collapse: collapse;
			margin-top: 8px;
		}}
		table.et-table th {{
			background: {HM_BLUE};
			color: #fff;
			padding: 6px 8px;
			font-size: 11px;
			text-align: {opp_align};
		}}
		table.et-table th:first-child, table.et-table td:first-child {{
			text-align: {align};
		}}
		table.et-table td {{
			padding: 5px 8px;
			font-size: 11px;
			border-bottom: 1px solid #e5e5e5;
			text-align: {opp_align};
		}}
		tr.et-group td {{ font-weight: 600; background: #f4f6fb; }}
		tr.et-total td {{ font-weight: 700; border-top: 2px solid {HM_BLUE}; }}
		.neg {{ color: {HM_RED}; }}
		.et-kpis {{ display: flex; gap: 12px; margin: 16px 0; }}
		.et-kpi {{
			flex: 1; border: 1px solid #e0e0e0; border-radius: 6px;
			padding: 10px 12px; text-align: center;
		}}
		.et-kpi .label {{ font-size: 10px; color: #777; text-transform: uppercase; }}
		.et-kpi .value {{ font-size: 16px; font-weight: 700; color: {HM_BLUE}; margin-top: 4px; }}
		.et-txn-row td {{ background: #fafafa; font-size: 10px; padding-left: 24px; }}
		@media print {{
			.no-print {{ display: none; }}
		}}
	"""


def _fmt(value, currency):
	value = flt(value)
	formatted = frappe.utils.fmt_money(value, currency=currency)
	if value < 0:
		return f'<span class="neg">{formatted}</span>'
	return formatted


def _header_html(labels, filters, company, is_ar):
	company_name = company.company_name if company else filters.get("company")
	trn = getattr(company, "tax_id", None) or ""
	return f"""
		<div class="et-header">
			<div>
				<h1>{labels['title']}</h1>
				<div>{company_name}{f" &middot; TRN {trn}" if trn else ""}</div>
			</div>
			<div class="meta">
				{labels['period']}: {formatdate(filters.get('from_date'))} — {formatdate(filters.get('to_date'))}
			</div>
		</div>
	"""


def _visible_rows(data):
	# strip the blank spacer dict the standard report inserts before the total row
	return [d for d in data if d and d.get("account")]


def _render_standard(data, labels, currency, is_ar):
	rows = _visible_rows(data)
	body_rows = ""
	for d in rows:
		is_total = d["account"].strip("'") == labels["total"] if isinstance(d["account"], str) else False
		css_class = "et-total" if is_total or d["account"] == "'" + _("Total") + "'" else (
			"et-group" if d.get("is_group") else ""
		)
		indent_px = (d.get("indent", 0) or 0) * 18
		name = d.get("account_name", d["account"])
		body_rows += f"""
			<tr class="{css_class}">
				<td style="padding-{'right' if is_ar else 'left'}:{indent_px}px">{name}</td>
				<td>{_fmt(d.get('opening_debit'), currency)}</td>
				<td>{_fmt(d.get('opening_credit'), currency)}</td>
				<td>{_fmt(d.get('debit'), currency)}</td>
				<td>{_fmt(d.get('credit'), currency)}</td>
				<td>{_fmt(d.get('closing_debit'), currency)}</td>
				<td>{_fmt(d.get('closing_credit'), currency)}</td>
			</tr>
		"""
	return f"""
		<table class="et-table">
			<thead><tr>
				<th>{labels['account']}</th>
				<th>{labels['opening_dr']}</th>
				<th>{labels['opening_cr']}</th>
				<th>{labels['debit']}</th>
				<th>{labels['credit']}</th>
				<th>{labels['closing_dr']}</th>
				<th>{labels['closing_cr']}</th>
			</tr></thead>
			<tbody>{body_rows}</tbody>
		</table>
	"""


def _render_detailed(data, labels, currency, is_ar, filters):
	rows = _visible_rows(data)
	body_rows = ""
	for d in rows:
		is_total = d["account"] == "'" + _("Total") + "'"
		css_class = "et-total" if is_total else ("et-group" if d.get("is_group") else "")
		indent_px = (d.get("indent", 0) or 0) * 18
		name = d.get("account_name", d["account"])
		body_rows += f"""
			<tr class="{css_class}">
				<td style="padding-{'right' if is_ar else 'left'}:{indent_px}px">{name}</td>
				<td>{_fmt(d.get('opening_debit'), currency)}</td>
				<td>{_fmt(d.get('opening_credit'), currency)}</td>
				<td>{_fmt(d.get('debit'), currency)}</td>
				<td>{_fmt(d.get('credit'), currency)}</td>
				<td>{_fmt(d.get('closing_debit'), currency)}</td>
				<td>{_fmt(d.get('closing_credit'), currency)}</td>
			</tr>
		"""
		# nested transactions for leaf accounts with movement in the period
		if not is_total and not d.get("is_group") and (flt(d.get("debit")) or flt(d.get("credit"))):
			txns = get_account_transactions(
				account=d["account"],
				company=filters.get("company"),
				from_date=filters.get("from_date"),
				to_date=filters.get("to_date"),
				party_type=filters.get("party_type"),
				party=filters.get("party"),
				cost_center=filters.get("cost_center"),
				project=filters.get("project"),
				voucher_type=filters.get("voucher_type"),
				voucher_no=filters.get("voucher_no"),
			)
			for t in txns:
				body_rows += f"""
					<tr class="et-txn-row">
						<td colspan="3">
							{formatdate(t.posting_date)} &middot; {t.voucher_type} {t.voucher_no}
							{f" &middot; {t.party}" if t.party else ""}
						</td>
						<td>{_fmt(t.debit, currency)}</td>
						<td>{_fmt(t.credit, currency)}</td>
						<td colspan="2"></td>
					</tr>
				"""
	return f"""
		<table class="et-table">
			<thead><tr>
				<th>{labels['account']}</th>
				<th>{labels['opening_dr']}</th>
				<th>{labels['opening_cr']}</th>
				<th>{labels['debit']}</th>
				<th>{labels['credit']}</th>
				<th>{labels['closing_dr']}</th>
				<th>{labels['closing_cr']}</th>
			</tr></thead>
			<tbody>{body_rows}</tbody>
		</table>
	"""


def _render_summary(data, labels, currency, is_ar):
	# group by root_type using the top-level (indent 0) rows only, since
	# their closing totals already carry the full subtree via
	# accumulate_values_into_parents — avoids double counting.
	rows = _visible_rows(data)
	roots = [d for d in rows if (d.get("indent") or 0) == 0 and d.get("root_type")]

	totals_by_root = {}
	for d in roots:
		rt = d["root_type"]
		totals_by_root.setdefault(rt, {"closing_debit": 0.0, "closing_credit": 0.0})
		totals_by_root[rt]["closing_debit"] += flt(d.get("closing_debit"))
		totals_by_root[rt]["closing_credit"] += flt(d.get("closing_credit"))

	assets = totals_by_root.get("Asset", {}).get("closing_debit", 0) - totals_by_root.get("Asset", {}).get(
		"closing_credit", 0
	)
	liabilities = totals_by_root.get("Liability", {}).get("closing_credit", 0) - totals_by_root.get(
		"Liability", {}
	).get("closing_debit", 0)
	equity = totals_by_root.get("Equity", {}).get("closing_credit", 0) - totals_by_root.get("Equity", {}).get(
		"closing_debit", 0
	)
	income = totals_by_root.get("Income", {}).get("closing_credit", 0) - totals_by_root.get("Income", {}).get(
		"closing_debit", 0
	)
	expense = totals_by_root.get("Expense", {}).get("closing_debit", 0) - totals_by_root.get("Expense", {}).get(
		"closing_credit", 0
	)
	net_income = income - expense

	kpis = f"""
		<div class="et-kpis">
			<div class="et-kpi"><div class="label">{labels['assets']}</div><div class="value">{_fmt(assets, currency)}</div></div>
			<div class="et-kpi"><div class="label">{labels['liabilities']}</div><div class="value">{_fmt(liabilities, currency)}</div></div>
			<div class="et-kpi"><div class="label">{labels['equity']}</div><div class="value">{_fmt(equity, currency)}</div></div>
			<div class="et-kpi"><div class="label">{labels['net_income']}</div><div class="value">{_fmt(net_income, currency)}</div></div>
		</div>
	"""

	body_rows = ""
	for rt, totals in totals_by_root.items():
		label = labels.get(ROOT_TYPE_LABEL_KEY.get(rt, ""), rt)
		body_rows += f"""
			<tr class="et-group">
				<td>{label}</td>
				<td>{_fmt(totals['closing_debit'], currency)}</td>
				<td>{_fmt(totals['closing_credit'], currency)}</td>
			</tr>
		"""

	table = f"""
		<table class="et-table">
			<thead><tr>
				<th>{labels['account']}</th>
				<th>{labels['closing_dr']}</th>
				<th>{labels['closing_cr']}</th>
			</tr></thead>
			<tbody>{body_rows}</tbody>
		</table>
	"""
	return kpis + table


@frappe.whitelist()
def get_print_html(filters, print_design="standard", language="en"):
	filters = frappe._dict(json.loads(filters) if isinstance(filters, str) else filters)
	is_ar = language == "ar"
	labels = LABELS["ar"] if is_ar else LABELS["en"]

	# executive summary always shows the full unfiltered tree, since its
	# subtotals rely on true root accounts (indent 0)
	summary_filters = frappe._dict(filters)
	if print_design == "summary":
		summary_filters.level = None
		summary_filters.only_ledger_accounts = 0
		summary_filters.account_type = None

	columns, data = execute(summary_filters if print_design == "summary" else filters)
	data = data or []

	company = frappe.get_cached_doc("Company", filters.company) if filters.get("company") else None
	currency = filters.get("presentation_currency") or erpnext.get_company_currency(filters.company)

	if print_design == "detailed":
		body = _render_detailed(data, labels, currency, is_ar, filters)
	elif print_design == "summary":
		body = _render_summary(data, labels, currency, is_ar)
	else:
		body = _render_standard(data, labels, currency, is_ar)

	html = f"""
		<html dir="{'rtl' if is_ar else 'ltr'}">
		<head>
			<meta charset="utf-8">
			<title>{labels['title']}</title>
			<style>{_base_css(is_ar)}</style>
		</head>
		<body>
			{_header_html(labels, filters, company, is_ar)}
			{body}
		</body>
		</html>
	"""
	return html


@frappe.whitelist()
def download_pdf(filters, print_design="standard", language="en"):
	html = get_print_html(filters, print_design, language)
	frappe.local.response.filecontent = get_pdf(html)
	frappe.local.response.type = "download"
	frappe.local.response.filename = f"ET Trial Balance - {print_design}.pdf"