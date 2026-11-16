# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Category"), "fieldname": "category", "fieldtype": "Link", "options": "Equipment Category", "width": 170},
		{"label": _("Tracking"), "fieldname": "tracking_type", "fieldtype": "Data", "width": 90},
		{"label": _("Site / Branch"), "fieldname": "site", "fieldtype": "Link", "options": "Branch", "width": 140},
		{"label": _("In Stock"), "fieldname": "in_stock", "fieldtype": "Float", "width": 90},
		{"label": _("Issued"), "fieldname": "issued", "fieldtype": "Float", "width": 90},
		{"label": _("In Repair"), "fieldname": "in_repair", "fieldtype": "Float", "width": 90},
		{"label": _("Lost"), "fieldname": "lost", "fieldtype": "Float", "width": 80},
		{"label": _("Scrapped"), "fieldname": "scrapped", "fieldtype": "Float", "width": 90},
		{"label": _("Total"), "fieldname": "total", "fieldtype": "Float", "width": 90},
	]


def get_data(filters):
	values = {}
	eq_conditions = ""
	ledger_conditions = ""
	if filters.get("company"):
		eq_conditions += " and eq.company = %(company)s"
		ledger_conditions += " and l.company = %(company)s"
		values["company"] = filters.company
	if filters.get("site"):
		eq_conditions += " and eq.site = %(site)s"
		ledger_conditions += " and l.site = %(site)s"
		values["site"] = filters.site
	if filters.get("category"):
		eq_conditions += " and eq.category = %(category)s"
		ledger_conditions += " and l.category = %(category)s"
		values["category"] = filters.category

	serialized = frappe.db.sql(
		f"""
		select eq.category, 'Serialized' as tracking_type, eq.site,
			sum(eq.status = 'In Stock') as in_stock,
			sum(eq.status = 'Issued') as issued,
			sum(eq.status = 'In Repair') as in_repair,
			sum(eq.status = 'Lost') as lost,
			sum(eq.status = 'Scrapped') as scrapped,
			count(*) as total
		from `tabEquipment` eq
		where 1 = 1 {eq_conditions}
		group by eq.category, eq.site
		""",
		values,
		as_dict=True,
	)

	quantity = frappe.db.sql(
		f"""
		select l.category, 'Quantity' as tracking_type, l.site,
			sum(l.stock_effect) as in_stock,
			sum(l.custody_effect) as issued,
			0 as in_repair, 0 as lost, 0 as scrapped,
			sum(l.stock_effect) + sum(l.custody_effect) as total
		from `tabEquipment Ledger` l
		inner join `tabEquipment Category` c on c.name = l.category
		where c.tracking_type = 'Quantity' {ledger_conditions}
		group by l.category, l.site
		""",
		values,
		as_dict=True,
	)

	data = serialized + quantity
	data.sort(key=lambda d: (d.category or "", d.site or ""))
	return data
