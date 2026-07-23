# Copyright (c) 2026, HM and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	chart = get_chart(data)
	summary = get_report_summary(data)
	return columns, data, None, chart, summary


def get_columns():
	return [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link",
			"options": "Employee", "width": 110},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link",
			"options": "Department", "width": 150},
		{"label": _("Designation"), "fieldname": "designation", "fieldtype": "Link",
			"options": "Designation", "width": 130},
		{"label": _("Date of Joining"), "fieldname": "date_of_joining", "fieldtype": "Date", "width": 100},
		{"label": _("Leave Type"), "fieldname": "leave_type", "fieldtype": "Link",
			"options": "Leave Type", "width": 130},
		{"label": _("Leave Balance (Days)"), "fieldname": "leave_balance", "fieldtype": "Float",
			"precision": 2, "width": 150},
		{"label": _("Daily Rate (SAR)"), "fieldname": "daily_rate", "fieldtype": "Currency",
			"options": "currency", "width": 120},
		{"label": _("Leave Liability (SAR)"), "fieldname": "leave_liability", "fieldtype": "Currency",
			"options": "currency", "width": 160},
		{"label": _("Currency"), "fieldname": "currency", "fieldtype": "Data", "width": 70, "hidden": 1},
	]


def get_data(filters):
	employees = get_employees(filters)
	if not employees:
		return []

	emp_names = [e.name for e in employees]
	leave_types = get_leave_types(filters)
	if not leave_types:
		return []

	as_on_date = filters.get("as_on_date") or nowdate()

	balances = get_leave_balances(emp_names, leave_types, as_on_date)
	daily_rates = get_daily_rates(emp_names, as_on_date, filters)

	data = []
	for emp in employees:
		emp_balances = balances.get(emp.name, {})
		if not emp_balances:
			continue

		daily_rate = daily_rates.get(emp.name, 0)

		for leave_type, bal in emp_balances.items():
			bal = flt(bal, 2)
			if bal <= 0 and not filters.get("show_zero_balance"):
				continue

			data.append({
				"employee": emp.name,
				"employee_name": emp.employee_name,
				"department": emp.department,
				"designation": emp.designation,
				"date_of_joining": emp.date_of_joining,
				"leave_type": leave_type,
				"leave_balance": bal,
				"daily_rate": daily_rate,
				"leave_liability": flt(bal * daily_rate, 2),
				"currency": "SAR",
			})

	data.sort(key=lambda r: (r["employee_name"] or "", r["leave_type"] or ""))
	return data


def get_employees(filters):
	conditions = ["status = 'Active'"]
	values = {}

	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters.company
	if filters.get("employee"):
		conditions.append("name = %(employee)s")
		values["employee"] = filters.employee
	if filters.get("department"):
		conditions.append("department = %(department)s")
		values["department"] = filters.department

	return frappe.db.sql("""
		select name, employee_name, department, designation, date_of_joining, company
		from `tabEmployee`
		where {conditions}
		order by employee_name
	""".format(conditions=" and ".join(conditions)), values, as_dict=True)


def get_leave_types(filters):
	conditions = []
	values = {}

	if filters.get("leave_type"):
		conditions.append("name = %(leave_type)s")
		values["leave_type"] = filters.leave_type
	elif not filters.get("include_lwp"):
		conditions.append("is_lwp = 0")

	where_clause = " and ".join(conditions) if conditions else "1=1"

	rows = frappe.db.sql("""
		select name from `tabLeave Type` where {conditions}
	""".format(conditions=where_clause), values, as_dict=True)

	return [r.name for r in rows]


def get_leave_balances(employees, leave_types, as_on_date):
	"""
	Sums Leave Ledger Entry rather than calling get_leave_balance_on() per
	employee/leave-type, since that is far too slow for a report covering
	the whole headcount. This is accurate as long as the leave allocation
	expiry job has run, since Frappe HR posts an offsetting negative entry
	in the ledger when an allocation expires - so a straight SUM nets out
	correctly. If you need bullet-proof parity with the Leave Application
	balance widget (e.g. mid-migration data), swap this for
	hrms.hr.doctype.leave_application.leave_application.get_leave_balance_on
	inside a loop, at the cost of speed.
	"""
	if not employees or not leave_types:
		return {}

	rows = frappe.db.sql("""
		select employee, leave_type, sum(leaves) as balance
		from `tabLeave Ledger Entry`
		where docstatus = 1
			and employee in %(employees)s
			and leave_type in %(leave_types)s
			and to_date <= %(as_on_date)s
		group by employee, leave_type
	""", {
		"employees": employees,
		"leave_types": leave_types,
		"as_on_date": as_on_date,
	}, as_dict=True)

	balances = {}
	for r in rows:
		balances.setdefault(r.employee, {})[r.leave_type] = r.balance

	return balances


def get_daily_rates(employees, as_on_date, filters):
	"""
	Daily rate = monthly amount / days_divisor (KSA convention: 30).
	Two selectable bases:
	  - Basic Salary (Structure): the `base` field on the latest submitted
	    Salary Structure Assignment as of the report date. Cheap, always
	    available, matches the common EOSB/leave-encashment practice of
	    basing accruals on basic pay only.
	  - Gross Pay (Latest Salary Slip): gross_pay from the most recent
	    submitted Salary Slip on/before the report date. Picks up
	    allowances actually paid, at the cost of being slip-dependent
	    (an employee with no slips yet will show 0).
	"""
	if not employees:
		return {}

	divisor = flt(filters.get("days_divisor")) or 30
	salary_basis = filters.get("salary_basis") or "Basic Salary (Structure)"

	if salary_basis == "Gross Pay (Latest Salary Slip)":
		rows = frappe.db.sql("""
			select employee, amount from (
				select ss.employee, ss.gross_pay as amount,
					row_number() over (partition by ss.employee order by ss.end_date desc) as rn
				from `tabSalary Slip` ss
				where ss.employee in %(employees)s
					and ss.docstatus = 1
					and ss.end_date <= %(as_on_date)s
			) ranked
			where rn = 1
		""", {"employees": employees, "as_on_date": as_on_date}, as_dict=True)
	else:
		rows = frappe.db.sql("""
			select employee, amount from (
				select ssa.employee, ssa.base as amount,
					row_number() over (partition by ssa.employee order by ssa.from_date desc) as rn
				from `tabSalary Structure Assignment` ssa
				where ssa.employee in %(employees)s
					and ssa.docstatus = 1
					and ssa.from_date <= %(as_on_date)s
			) ranked
			where rn = 1
		""", {"employees": employees, "as_on_date": as_on_date}, as_dict=True)

	return {r.employee: flt(flt(r.amount) / divisor, 2) for r in rows}


def get_chart(data):
	if not data:
		return None

	dept_totals = {}
	for row in data:
		dept = row.get("department") or _("Unassigned")
		dept_totals[dept] = dept_totals.get(dept, 0) + flt(row.get("leave_liability"))

	return {
		"data": {
			"labels": list(dept_totals.keys()),
			"datasets": [{"name": _("Leave Liability (SAR)"), "values": [flt(v, 2) for v in dept_totals.values()]}],
		},
		"type": "bar",
		"colors": ["#010BCE"],
	}


def get_report_summary(data):
	if not data:
		return []

	total_liability = sum(flt(d.get("leave_liability")) for d in data)
	total_days = sum(flt(d.get("leave_balance")) for d in data)
	emp_count = len({d.get("employee") for d in data})

	return [
		{"value": emp_count, "label": _("Employees"), "datatype": "Int"},
		{"value": flt(total_days, 2), "label": _("Total Leave Days"), "datatype": "Float"},
		{"value": flt(total_liability, 2), "label": _("Total Liability"),
			"datatype": "Currency", "currency": "SAR"},
	]