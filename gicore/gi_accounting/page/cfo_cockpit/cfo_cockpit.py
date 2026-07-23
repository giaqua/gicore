import frappe
from frappe import _
from frappe.utils import nowdate, add_days, getdate, flt


def _check_permission():
	if not (
		frappe.has_permission("Sales Invoice", "read")
		and frappe.has_permission("Purchase Invoice", "read")
		and frappe.has_permission("GL Entry", "read")
	):
		frappe.throw(_("Not permitted to view the CFO Cockpit"), frappe.PermissionError)


@frappe.whitelist()
def get_cockpit_data(company, weeks=8):
	"""Single call that feeds the whole page."""
	_check_permission()

	weeks = int(weeks)
	cash_bank = get_cash_bank_position(company)
	ar = get_receivables_aging(company)
	ap = get_payables_aging(company)
	forecast = get_cash_flow_forecast(company, cash_bank.get("total"), weeks)

	return {
		"cash_bank": cash_bank,
		"ar": ar,
		"ap": ap,
		"forecast": forecast,
		"as_on": nowdate(),
	}


def get_cash_bank_position(company):
	accounts = frappe.db.sql(
		"""
		select a.name as account, a.account_currency
		from `tabAccount` a
		where a.company=%s and a.account_type in ('Bank', 'Cash')
			and a.is_group=0 and a.disabled=0
		""",
		company,
		as_dict=True,
	)

	if not accounts:
		return {"accounts": [], "total": 0}

	account_names = [a.account for a in accounts]

	balances = frappe.db.sql(
		"""
		select account, sum(debit - credit) as balance
		from `tabGL Entry`
		where company=%s and is_cancelled=0 and account in %s
		group by account
		""",
		(company, account_names),
		as_dict=True,
	)

	balance_map = {b.account: flt(b.balance) for b in balances}

	rows, total = [], 0
	for a in accounts:
		bal = balance_map.get(a.account, 0)
		total += bal
		rows.append({"account": a.account, "balance": bal, "currency": a.account_currency})

	rows.sort(key=lambda r: r["balance"], reverse=True)
	return {"accounts": rows, "total": total}


def _aging_buckets(rows, party_field):
	today = getdate(nowdate())
	buckets = {"not_due": 0, "1_30": 0, "31_60": 0, "61_90": 0, "90_plus": 0}
	party_totals = {}

	for r in rows:
		due = getdate(r.due_date) if r.due_date else today
		days = (today - due).days
		amt = flt(r.outstanding_amount)

		if days <= 0:
			buckets["not_due"] += amt
		elif days <= 30:
			buckets["1_30"] += amt
		elif days <= 60:
			buckets["31_60"] += amt
		elif days <= 90:
			buckets["61_90"] += amt
		else:
			buckets["90_plus"] += amt

		if days > 0:
			party = r.get(party_field)
			party_totals[party] = party_totals.get(party, 0) + amt

	top_overdue = sorted(
		[{"party": k, "overdue": v} for k, v in party_totals.items()],
		key=lambda x: x["overdue"],
		reverse=True,
	)[:10]

	return {"buckets": buckets, "top_overdue": top_overdue, "total": sum(buckets.values())}


def get_receivables_aging(company):
	rows = frappe.db.sql(
		"""
		select customer, due_date, outstanding_amount
		from `tabSales Invoice`
		where company=%s and docstatus=1 and outstanding_amount > 0
		""",
		company,
		as_dict=True,
	)
	return _aging_buckets(rows, "customer")


def get_payables_aging(company):
	rows = frappe.db.sql(
		"""
		select supplier, due_date, outstanding_amount
		from `tabPurchase Invoice`
		where company=%s and docstatus=1 and outstanding_amount > 0
		""",
		company,
		as_dict=True,
	)
	return _aging_buckets(rows, "supplier")


def get_cash_flow_forecast(company, opening_balance, weeks=8):
	"""
	Simple weekly-bucket forecast: opening cash + expected AR collections
	- expected AP payments, based on due_date. Assumes on-time settlement,
	so treat it as a directional projection, not a guarantee.
	"""
	today = getdate(nowdate())
	weeks = int(weeks)

	ar_rows = frappe.db.sql(
		"""
		select due_date, outstanding_amount
		from `tabSales Invoice`
		where company=%s and docstatus=1 and outstanding_amount > 0
		""",
		company,
		as_dict=True,
	)

	ap_rows = frappe.db.sql(
		"""
		select due_date, outstanding_amount
		from `tabPurchase Invoice`
		where company=%s and docstatus=1 and outstanding_amount > 0
		""",
		company,
		as_dict=True,
	)

	buckets = []
	running = flt(opening_balance)

	for i in range(weeks):
		week_start = getdate(add_days(today, i * 7))
		week_end = getdate(add_days(today, i * 7 + 6))

		if i == 0:
			# first bucket sweeps up anything already overdue too
			inflow = sum(flt(r.outstanding_amount) for r in ar_rows if getdate(r.due_date) <= week_end)
			outflow = sum(flt(r.outstanding_amount) for r in ap_rows if getdate(r.due_date) <= week_end)
		else:
			inflow = sum(
				flt(r.outstanding_amount) for r in ar_rows if week_start <= getdate(r.due_date) <= week_end
			)
			outflow = sum(
				flt(r.outstanding_amount) for r in ap_rows if week_start <= getdate(r.due_date) <= week_end
			)

		running += inflow - outflow
		buckets.append(
			{
				"week_start": str(week_start),
				"week_end": str(week_end),
				"inflow": inflow,
				"outflow": outflow,
				"net": inflow - outflow,
				"projected_balance": running,
			}
		)

	return {"opening_balance": flt(opening_balance), "weeks": buckets}