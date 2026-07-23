# Copyright (c) 2026, HM and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import add_days, flt, fmt_money, getdate, nowdate

FORECAST_BUCKETS = [
	{"key": "overdue", "label": _("Overdue")},
	{"key": "b0_7", "label": _("0-7 Days")},
	{"key": "b8_30", "label": _("8-30 Days")},
	{"key": "b31_60", "label": _("31-60 Days")},
	{"key": "b61_90", "label": _("61-90 Days")},
	{"key": "b90_plus", "label": _("90+ Days")},
]

DATE_FORMATS = {
	"Daily": "%Y-%m-%d",
	"Weekly": "%x-%v",
	"Monthly": "%Y-%m",
}


def execute(filters=None):
	filters = frappe._dict(filters or {})
	validate_filters(filters)

	view = filters.get("view") or "Cash Position"

	columns = get_columns(view)
	data = get_data(view, filters)
	chart = get_chart(view, filters)
	report_summary = get_report_summary(filters)

	return columns, data, None, chart, report_summary


def validate_filters(filters):
	if not filters.get("company"):
		frappe.throw(_("Company is mandatory"))

	if not filters.get("as_on_date"):
		filters.as_on_date = nowdate()

	if (filters.get("view") or "Cash Position") == "Historical Trend":
		from_date = filters.get("from_date") or add_days(filters.as_on_date, -90)
		if getdate(from_date) > getdate(filters.as_on_date):
			frappe.throw(_("Trend From Date cannot be after As On Date"))
		filters.from_date = from_date


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def get_cash_accounts(filters):
	conditions = ["a.account_type in ('Bank', 'Cash')", "a.is_group = 0", "a.company = %(company)s"]
	values = {"company": filters.company}

	if filters.get("account"):
		conditions.append("a.name = %(account)s")
		values["account"] = filters.account

	if filters.get("currency"):
		conditions.append("a.account_currency = %(currency)s")
		values["currency"] = filters.currency

	condition_str = " and ".join(conditions)

	return frappe.db.sql(
		f"""
		select
			a.name as account,
			a.account_name,
			a.account_type,
			a.account_currency,
			a.company,
			ba.bank as bank,
			ba.disabled as is_disabled
		from `tabAccount` a
		left join `tabBank Account` ba on ba.account = a.name
		where {condition_str}
		order by a.account_type, a.account_name
		""",
		values,
		as_dict=True,
	)


def get_account_balances(accounts, filters):
	if not accounts:
		return {}

	account_names = [a.account for a in accounts]

	gl_data = frappe.db.sql(
		"""
		select
			account,
			sum(debit - credit) as balance,
			sum(debit_in_account_currency - credit_in_account_currency) as balance_in_account_currency
		from `tabGL Entry`
		where
			account in %(accounts)s
			and company = %(company)s
			and posting_date <= %(as_on_date)s
			and is_cancelled = 0
		group by account
		""",
		{
			"accounts": account_names,
			"company": filters.company,
			"as_on_date": filters.as_on_date,
		},
		as_dict=True,
	)

	return {d.account: d for d in gl_data}


def get_total_cash_balance(filters):
	accounts = get_cash_accounts(filters)
	balances = get_account_balances(accounts, filters)
	return sum(flt(b.balance) for b in balances.values())


def get_bucket_case_sql():
	return """
		case
			when datediff(due_date, %(as_on_date)s) < 0 then 'overdue'
			when datediff(due_date, %(as_on_date)s) between 0 and 7 then 'b0_7'
			when datediff(due_date, %(as_on_date)s) between 8 and 30 then 'b8_30'
			when datediff(due_date, %(as_on_date)s) between 31 and 60 then 'b31_60'
			when datediff(due_date, %(as_on_date)s) between 61 and 90 then 'b61_90'
			else 'b90_plus'
		end
	"""


def get_forecast_data(filters):
	values = {"company": filters.company, "as_on_date": filters.as_on_date}
	bucket_sql = get_bucket_case_sql()

	receipts = frappe.db.sql(
		f"""
		select {bucket_sql} as bucket, sum(outstanding_amount) as amount
		from `tabSales Invoice`
		where docstatus = 1 and company = %(company)s and outstanding_amount > 0
		group by bucket
		""",
		values,
		as_dict=True,
	)

	payments = frappe.db.sql(
		f"""
		select {bucket_sql} as bucket, sum(outstanding_amount) as amount
		from `tabPurchase Invoice`
		where docstatus = 1 and company = %(company)s and outstanding_amount > 0
		group by bucket
		""",
		values,
		as_dict=True,
	)

	receipts_map = {r.bucket: flt(r.amount) for r in receipts}
	payments_map = {p.bucket: flt(p.amount) for p in payments}

	opening_balance = get_total_cash_balance(filters)

	row_opening = {"category": _("Opening Cash Balance"), "total": opening_balance}
	row_receipts = {"category": _("Expected Receipts (AR)")}
	row_payments = {"category": _("Expected Payments (AP)")}
	row_net = {"category": _("Net Cash Flow")}
	row_projected = {"category": _("Projected Cash Balance")}

	running_balance = opening_balance
	total_receipts = 0
	total_payments = 0

	for bucket in FORECAST_BUCKETS:
		key = bucket["key"]
		r_amt = receipts_map.get(key, 0)
		p_amt = payments_map.get(key, 0)
		net = r_amt - p_amt
		running_balance += net

		row_receipts[key] = r_amt
		row_payments[key] = p_amt
		row_net[key] = net
		row_projected[key] = running_balance

		total_receipts += r_amt
		total_payments += p_amt

	row_receipts["total"] = total_receipts
	row_payments["total"] = total_payments
	row_net["total"] = total_receipts - total_payments
	row_projected["total"] = running_balance

	return [row_opening, row_receipts, row_payments, row_net, row_projected]


def get_trend_data(filters):
	accounts = get_cash_accounts(filters)
	account_names = [a.account for a in accounts]
	if not account_names:
		return []

	from_date = filters.get("from_date") or add_days(filters.as_on_date, -90)
	granularity = filters.get("granularity") or "Daily"
	date_format = DATE_FORMATS.get(granularity, "%%Y-%%m-%%d")

	opening = frappe.db.sql(
		"""
		select sum(debit - credit) as balance
		from `tabGL Entry`
		where account in %(accounts)s
			and company = %(company)s
			and posting_date < %(from_date)s
			and is_cancelled = 0
		""",
		{"accounts": account_names, "company": filters.company, "from_date": from_date},
		as_dict=True,
	)
	running_balance = flt(opening[0].balance) if opening else 0

	movements = frappe.db.sql(
		f"""
		select
			date_format(posting_date, '%%Y-%%m-%%d') as period,
			min(posting_date) as period_start,
			sum(case when (debit - credit) > 0 then (debit - credit) else 0 end) as inflow,
			sum(case when (debit - credit) < 0 then (credit - debit) else 0 end) as outflow,
			sum(debit - credit) as net_change
		from `tabGL Entry`
		where account in %(accounts)s
			and company = %(company)s
			and posting_date between %(from_date)s and %(as_on_date)s
			and is_cancelled = 0
		group by period
		order by period_start
		""",
		{
			"accounts": account_names,
			"company": filters.company,
			"from_date": from_date,
			"as_on_date": filters.as_on_date,
		},
		as_dict=True,
	)

	data = []
	for m in movements:
		running_balance += flt(m.net_change)
		data.append(
			{
				"period": m.period,
				"inflow": flt(m.inflow),
				"outflow": flt(m.outflow),
				"net_change": flt(m.net_change),
				"closing_balance": running_balance,
			}
		)

	return data


# ---------------------------------------------------------------------------
# Columns / Data dispatch
# ---------------------------------------------------------------------------

def get_columns(view):
	if view == "Cash Flow Forecast":
		columns = [{"label": _("Category"), "fieldname": "category", "fieldtype": "Data", "width": 220}]
		for bucket in FORECAST_BUCKETS:
			columns.append(
				{"label": bucket["label"], "fieldname": bucket["key"], "fieldtype": "Currency", "width": 130}
			)
		columns.append({"label": _("Total"), "fieldname": "total", "fieldtype": "Currency", "width": 140})
		return columns

	if view == "Historical Trend":
		return [
			{"label": _("Period"), "fieldname": "period", "fieldtype": "Data", "width": 110},
			{"label": _("Inflow"), "fieldname": "inflow", "fieldtype": "Currency", "width": 130},
			{"label": _("Outflow"), "fieldname": "outflow", "fieldtype": "Currency", "width": 130},
			{"label": _("Net Change"), "fieldname": "net_change", "fieldtype": "Currency", "width": 130},
			{"label": _("Closing Balance"), "fieldname": "closing_balance", "fieldtype": "Currency", "width": 150},
		]

	# Cash Position (default)
	return [
		{"label": _("Account"), "fieldname": "account", "fieldtype": "Link", "options": "Account", "width": 220},
		{"label": _("Account Name"), "fieldname": "account_name", "fieldtype": "Data", "width": 180},
		{"label": _("Type"), "fieldname": "account_type", "fieldtype": "Data", "width": 90},
		{"label": _("Bank"), "fieldname": "bank", "fieldtype": "Data", "width": 130},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "width": 90},
		{
			"label": _("Balance (Account Currency)"),
			"fieldname": "balance_account_currency",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 180,
		},
		{
			"label": _("Balance (Company Currency)"),
			"fieldname": "balance_company_currency",
			"fieldtype": "Currency",
			"width": 180,
		},
		{"label": _("% of Total"), "fieldname": "percent_of_total", "fieldtype": "Percent", "width": 100},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
	]


def get_data(view, filters):
	if view == "Cash Flow Forecast":
		return get_forecast_data(filters)

	if view == "Historical Trend":
		return get_trend_data(filters)

	return get_cash_position_data(filters)


def get_cash_position_data(filters):
	accounts = get_cash_accounts(filters)
	balances = get_account_balances(accounts, filters)

	data = []
	total_balance = 0

	for acc in accounts:
		bal = balances.get(acc.account) or frappe._dict({"balance": 0, "balance_in_account_currency": 0})
		balance = flt(bal.balance)
		total_balance += balance

		data.append(
			{
				"account": acc.account,
				"account_name": acc.account_name,
				"account_type": acc.account_type,
				"bank": acc.bank or "",
				"currency": acc.account_currency,
				"balance_account_currency": flt(bal.balance_in_account_currency),
				"balance_company_currency": balance,
				"status": _("Disabled") if acc.is_disabled else _("Active"),
			}
		)

	for row in data:
		row["percent_of_total"] = (
			flt(row["balance_company_currency"] / total_balance * 100, 2) if total_balance else 0
		)

	data.sort(key=lambda r: r["balance_company_currency"], reverse=True)

	if data:
		data.append(
			{
				"account_name": _("Total"),
				"balance_company_currency": total_balance,
				"percent_of_total": 100.0,
				"bold": 1,
			}
		)

	return data


# ---------------------------------------------------------------------------
# Chart
# ---------------------------------------------------------------------------

def get_chart(view, filters):
	if view == "Historical Trend":
		data = get_trend_data(filters)
		if not data:
			return None
		return {
			"data": {
				"labels": [d["period"] for d in data],
				"datasets": [
					{"name": _("Closing Balance"), "values": [d["closing_balance"] for d in data]},
					{"name": _("Net Change"), "values": [d["net_change"] for d in data]},
				],
			},
			"type": "line",
			"colors": ["#010BCE", "#D50000"],
		}

	if view == "Cash Flow Forecast":
		rows = get_forecast_data(filters)
		projected_row = next((r for r in rows if r.get("category") == _("Projected Cash Balance")), None)
		if not projected_row:
			return None
		return {
			"data": {
				"labels": [b["label"] for b in FORECAST_BUCKETS],
				"datasets": [
					{
						"name": _("Projected Balance"),
						"values": [projected_row.get(b["key"], 0) for b in FORECAST_BUCKETS],
					}
				],
			},
			"type": "line",
			"colors": ["#010BCE"],
		}

	# Cash Position: top 10 accounts by balance
	accounts = get_cash_accounts(filters)
	balances = get_account_balances(accounts, filters)
	rows = sorted(
		(
			(a.account_name, flt((balances.get(a.account) or frappe._dict({"balance": 0})).balance))
			for a in accounts
		),
		key=lambda r: r[1],
		reverse=True,
	)[:10]

	if not rows:
		return None

	return {
		"data": {
			"labels": [r[0] for r in rows],
			"datasets": [{"name": _("Balance"), "values": [r[1] for r in rows]}],
		},
		"type": "bar",
		"colors": ["#010BCE"],
	}


# ---------------------------------------------------------------------------
# KPI cards (report_summary)
# ---------------------------------------------------------------------------

def get_report_summary(filters):
	accounts = get_cash_accounts(filters)
	balances = get_account_balances(accounts, filters)

	total_cash = 0
	total_bank = 0

	for acc in accounts:
		bal = flt((balances.get(acc.account) or frappe._dict({"balance": 0})).balance)
		if acc.account_type == "Cash":
			total_cash += bal
		else:
			total_bank += bal

	total_position = total_cash + total_bank

	forecast_rows = get_forecast_data(filters)
	net_row = next((r for r in forecast_rows if r.get("category") == _("Net Cash Flow")), {})
	net_30 = flt(net_row.get("b0_7", 0)) + flt(net_row.get("b8_30", 0))
	projected_30 = total_position + net_30

	company_currency = frappe.get_cached_value("Company", filters.company, "default_currency")
	active_accounts = len([a for a in accounts if not a.is_disabled])

	return [
		{
			"label": _("Total Cash & Bank"),
			"value": fmt_money(total_position, currency=company_currency),
			"indicator": "Blue",
		},
		{
			"label": _("Bank Balance"),
			"value": fmt_money(total_bank, currency=company_currency),
			"indicator": "Blue",
		},
		{
			"label": _("Cash in Hand"),
			"value": fmt_money(total_cash, currency=company_currency),
			"indicator": "Blue",
		},
		{
			"label": _("Projected Balance (30 Days)"),
			"value": fmt_money(projected_30, currency=company_currency),
			"indicator": "Green" if projected_30 >= 0 else "Red",
		},
		{
			"label": _("Net Change (30 Days)"),
			"value": fmt_money(net_30, currency=company_currency),
			"indicator": "Green" if net_30 >= 0 else "Red",
		},
		{
			"label": _("Active Cash/Bank Accounts"),
			"value": active_accounts,
			"indicator": "Blue",
		},
	]