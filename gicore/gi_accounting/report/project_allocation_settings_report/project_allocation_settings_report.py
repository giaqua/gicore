import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
	filters = frappe._dict(filters or {})
	view_type = filters.get("view_type") or "Detail"

	settings = get_settings(filters)
	detail_rows = build_detail_rows(settings, filters)

	if view_type == "Summary (Lump Sum)":
		return get_summary_columns(), build_summary_rows(detail_rows)

	return get_detail_columns(), detail_rows


def get_detail_columns():
	return [
		{"label": _("Source Project"), "fieldname": "source_project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": _("From Date"), "fieldname": "start_date", "fieldtype": "Date", "width": 95},
		{"label": _("To Date"), "fieldname": "end_date", "fieldtype": "Date", "width": 95},
		{"label": _("Source Expense Account"), "fieldname": "source_account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("Total Debit"), "fieldname": "source_debit", "fieldtype": "Currency", "width": 110},
		{"label": _("Total Credit"), "fieldname": "source_credit", "fieldtype": "Currency", "width": 110},
		{"label": _("Period Total Amount"), "fieldname": "source_cost", "fieldtype": "Currency", "width": 140},
		{"label": _("Target Project"), "fieldname": "target_project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": _("Allocation %"), "fieldname": "percentage", "fieldtype": "Percent", "width": 110},
		{"label": _("Allocated Amount"), "fieldname": "allocated_amount", "fieldtype": "Currency", "width": 140},
		{"label": _("Target Expense Account"), "fieldname": "expense_account", "fieldtype": "Link", "options": "Account", "width": 180},
		{"label": _("Already Posted"), "fieldname": "already_posted", "fieldtype": "Data", "width": 110},
	]


def get_summary_columns():
	return [
		{"label": _("Target Project"), "fieldname": "target_project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": _("Source Project"), "fieldname": "source_project", "fieldtype": "Link", "options": "Project", "width": 150},
		{"label": _("Source Account"), "fieldname": "source_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Target Account"), "fieldname": "expense_account", "fieldtype": "Link", "options": "Account", "width": 170},
		{"label": _("Periods Included"), "fieldname": "period_count", "fieldtype": "Int", "width": 110},
		{"label": _("Total Allocated Amount"), "fieldname": "total_allocated", "fieldtype": "Currency", "width": 160},
		{"label": _("Breakdown"), "fieldname": "breakdown", "fieldtype": "Small Text", "width": 420},
	]


def build_detail_rows(settings, filters):
	"""One row per period (Settings record) per target project — e.g. a June row and
	a July row for the same project. Dates always come from the Settings record itself,
	not from the report's date filters (those only decide which records are shown)."""
	rows = []
	for setting in settings:
		start_date = setting.start_date
		end_date = setting.end_date

		source_cost, total_debit, total_credit = get_account_cost(
			setting.source_project, setting.source_expense_account,
			start_date, end_date, setting.company,
		)
		posted = is_period_posted(setting.source_project, start_date, end_date)

		targets = frappe.get_all(
			"HM Project Allocation Target",
			filters={"parent": setting.name},
			fields=["project", "percentage", "expense_account"],
			order_by="idx",
		)

		for t in targets:
			rows.append({
				"source_project": setting.source_project,
				"start_date": start_date,
				"end_date": end_date,
				"source_account": setting.source_expense_account,
				"source_debit": total_debit,
				"source_credit": total_credit,
				"source_cost": source_cost,
				"target_project": t.project,
				"percentage": t.percentage,
				"allocated_amount": flt(source_cost) * flt(t.percentage) / 100.0,
				"expense_account": t.expense_account,
				"already_posted": _("Yes") if posted else _("No"),
			})

	return rows


def build_summary_rows(detail_rows):
	"""Lump-sum view: group by (target project, source project, source account, target
	account) and sum the allocated amount across every period that combination appears
	in. E.g. Project1 = 30% of June's total + 40% of July's total, Project2 = 0% of
	June + 40% of July, each collapsed into one total. If a target project drew from
	different source projects/accounts across periods, those stay as separate rows
	rather than being mashed into one ambiguous total."""
	grouped = {}
	for row in detail_rows:
		key = (row["target_project"], row["source_project"], row["source_account"], row["expense_account"])
		if key not in grouped:
			grouped[key] = {
				"target_project": row["target_project"],
				"source_project": row["source_project"],
				"source_account": row["source_account"],
				"expense_account": row["expense_account"],
				"total_allocated": 0.0,
				"periods": [],
			}

		g = grouped[key]
		g["total_allocated"] += flt(row["allocated_amount"])
		g["periods"].append(
			"{0} to {1}: {2}% of {3} = {4}".format(
				row["start_date"], row["end_date"], row["percentage"],
				row["source_cost"], row["allocated_amount"],
			)
		)

	summary = []
	for g in grouped.values():
		summary.append({
			"target_project": g["target_project"],
			"source_project": g["source_project"],
			"source_account": g["source_account"],
			"expense_account": g["expense_account"],
			"period_count": len(g["periods"]),
			"total_allocated": g["total_allocated"],
			"breakdown": "; ".join(g["periods"]),
		})

	summary.sort(key=lambda r: r["total_allocated"], reverse=True)
	return summary


def get_settings(filters):
	"""Which Settings records to include. from_date/to_date, if given, filter by overlap
	with each record's own period — they never override the record's dates themselves."""
	conditions = ["is_active = 1"]
	values = {}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters.company
	if filters.get("source_project"):
		conditions.append("source_project = %(source_project)s")
		values["source_project"] = filters.source_project
	if filters.get("from_date"):
		conditions.append("end_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("start_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	where_clause = " and ".join(conditions)
	return frappe.db.sql(f"""
		select name, source_project, company, source_expense_account, start_date, end_date
		from `tabHM Project Allocation Settings`
		where {where_clause}
		order by start_date
	""", values, as_dict=True)


def get_account_cost(project, account, start_date, end_date, company):
	"""Step 1: fetch GL Entries for the account + period. Step 2: filter by project.
	Step 3: sum debit and credit. Step 4: net them."""
	gl_filters = {
		"account": account,
		"is_cancelled": 0,
		"posting_date": ["between", [start_date, end_date]],
	}
	if company:
		gl_filters["company"] = company

	entries = frappe.get_all(
		"GL Entry",
		filters=gl_filters,
		fields=["project", "debit", "credit"],
	)

	if project:
		entries = [e for e in entries if e.project == project]

	total_debit = sum(flt(e.debit) for e in entries)
	total_credit = sum(flt(e.credit) for e in entries)
	return total_debit - total_credit, total_debit, total_credit


def is_period_posted(source_project, start_date, end_date):
	"""Flags if a JE tagged with our allocation remark already exists for this project + period."""
	tag = _allocation_tag(source_project, start_date, end_date)
	return bool(frappe.db.exists("Journal Entry", {"user_remark": ["like", f"%{tag}%"], "docstatus": 1}))


def _allocation_tag(source_project, start_date, end_date):
	return f"[HM-ALLOC:{source_project}:{start_date}:{end_date}]"


@frappe.whitelist()
def post_allocation_journal_entry(source_project, posting_date=None):
	"""Called from the report's 'Post Journal Entry' button. Period always comes from
	the Settings record's own start_date/end_date — not from any report filter."""
	setting = frappe.get_doc("HM Project Allocation Settings", source_project)
	if not setting.is_active:
		frappe.throw(_("Allocation Settings for {0} are inactive.").format(source_project))

	from_date, to_date = setting.start_date, setting.end_date

	if is_period_posted(source_project, from_date, to_date):
		frappe.throw(_("An allocation JE for {0} in this period has already been posted.").format(source_project))

	source_cost, total_debit, total_credit = get_account_cost(
		source_project, setting.source_expense_account, from_date, to_date, setting.company
	)
	if not source_cost:
		frappe.throw(_("No cost found on account {0} for {1} in the selected period.").format(
			setting.source_expense_account, source_project
		))

	total_percent = sum(flt(t.percentage) for t in setting.allocation_targets)
	if abs(total_percent - 100.0) > 0.01:
		frappe.throw(_("Allocation percentages for {0} do not sum to 100%.").format(source_project))

	je = frappe.new_doc("Journal Entry")
	je.voucher_type = "Journal Entry"
	je.company = setting.company
	je.posting_date = posting_date or frappe.utils.today()
	je.user_remark = _("Project overhead allocation {0} (period {1} to {2})").format(
		_allocation_tag(source_project, from_date, to_date), from_date, to_date
	)

	je.append("accounts", {
		"account": setting.source_expense_account,
		"project": source_project,
		"credit_in_account_currency": source_cost,
	})

	for t in setting.allocation_targets:
		je.append("accounts", {
			"account": t.expense_account,
			"project": t.project,
			"debit_in_account_currency": flt(source_cost) * flt(t.percentage) / 100.0,
		})

	je.insert()
	je.submit()

	return je.name