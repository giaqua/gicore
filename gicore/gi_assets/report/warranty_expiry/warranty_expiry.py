# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, nowdate


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Equipment"), "fieldname": "name", "fieldtype": "Link", "options": "Equipment", "width": 110},
		{"label": _("Description"), "fieldname": "equipment_name", "fieldtype": "Data", "width": 190},
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Link", "options": "Equipment Category", "width": 130},
		{"label": _("Serial No"), "fieldname": "serial_no", "fieldtype": "Data", "width": 130},
		{"label": _("Warranty Expiry"), "fieldname": "warranty_expiry", "fieldtype": "Date", "width": 120},
		{"label": _("Days Left"), "fieldname": "days_left", "fieldtype": "Int", "width": 90},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 90},
		{"label": _("Custodian"), "fieldname": "custodian_name", "fieldtype": "Data", "width": 150},
	]


def get_data(filters):
	days = cint(filters.get("days")) or 90
	today = nowdate()

	conditions = ["warranty_expiry is not null", "status not in ('Scrapped', 'Lost')"]
	values = {"until": add_days(today, days), "today": today}

	if cint(filters.get("include_expired")):
		conditions.append("warranty_expiry <= %(until)s")
	else:
		conditions.append("warranty_expiry between %(today)s and %(until)s")
	if filters.get("category"):
		conditions.append("category = %(category)s")
		values["category"] = filters.category
	if filters.get("company"):
		conditions.append("company = %(company)s")
		values["company"] = filters.company

	data = frappe.db.sql(
		"select name, equipment_name, category, serial_no, warranty_expiry, status, custodian_name "
		"from `tabEquipment` where " + " and ".join(conditions) + " order by warranty_expiry",
		values,
		as_dict=True,
	)
	for row in data:
		row["days_left"] = date_diff(row.warranty_expiry, today)
	return data
