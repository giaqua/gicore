# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Employee"), "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 110},
		{"label": _("Employee Name"), "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 130},
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Link", "options": "Equipment Category", "width": 130},
		{"label": _("Equipment"), "fieldname": "equipment", "fieldtype": "Link", "options": "Equipment", "width": 110},
		{"label": _("Description"), "fieldname": "equipment_name", "fieldtype": "Data", "width": 170},
		{"label": _("Serial No"), "fieldname": "serial_no", "fieldtype": "Data", "width": 130},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 70},
		{"label": _("Condition"), "fieldname": "condition", "fieldtype": "Data", "width": 90},
		{"label": _("In Custody Since"), "fieldname": "since", "fieldtype": "Datetime", "width": 150},
	]


def get_data(filters):
	values = {}
	emp_conditions = []
	for key, column in (
		("employee", "e.name"),
		("department", "e.department"),
		("company", "e.company"),
		("employee_status", "e.status"),
	):
		if filters.get(key):
			emp_conditions.append(f"{column} = %({key})s")
			values[key] = filters[key]
	emp_sql = (" and " + " and ".join(emp_conditions)) if emp_conditions else ""

	category_sql = ""
	if filters.get("category"):
		category_sql = " and {alias}.category = %(category)s"
		values["category"] = filters.category

	serialized = frappe.db.sql(
		f"""
		select eq.current_custodian as employee, e.employee_name, e.department,
			eq.category, eq.name as equipment, eq.equipment_name, eq.serial_no,
			1 as qty, eq.`condition` as `condition`,
			(select max(l.posting_datetime) from `tabEquipment Ledger` l
				where l.equipment = eq.name and l.is_reversal = 0
				and l.movement_type in ('Issue', 'Transfer In')) as since
		from `tabEquipment` eq
		inner join `tabEmployee` e on e.name = eq.current_custodian
		where eq.status = 'Issued' {emp_sql} {category_sql.format(alias="eq")}
		""",
		values,
		as_dict=True,
	)

	quantity = frappe.db.sql(
		f"""
		select l.employee, e.employee_name, e.department, l.category,
			null as equipment, l.category as equipment_name, null as serial_no,
			sum(l.custody_effect) as qty, null as `condition`,
			max(case when l.movement_type in ('Issue', 'Transfer In') and l.is_reversal = 0
				then l.posting_datetime end) as since
		from `tabEquipment Ledger` l
		inner join `tabEmployee` e on e.name = l.employee
		inner join `tabEquipment Category` c on c.name = l.category
		where c.tracking_type = 'Quantity' {emp_sql} {category_sql.format(alias="l")}
		group by l.employee, l.category
		having sum(l.custody_effect) > 0
		""",
		values,
		as_dict=True,
	)

	data = serialized + quantity
	data.sort(key=lambda d: (d.employee or "", d.category or "", d.equipment or ""))
	return data
