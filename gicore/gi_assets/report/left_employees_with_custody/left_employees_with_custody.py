# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _

from gicore.gi_assets.report.custody_by_employee.custody_by_employee import (
	get_columns as base_columns,
)
from gicore.gi_assets.report.custody_by_employee.custody_by_employee import (
	get_data as base_data,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	filters.employee_status = "Left"

	columns = base_columns()
	columns.insert(
		2,
		{"label": _("Relieving Date"), "fieldname": "relieving_date", "fieldtype": "Date", "width": 110},
	)

	data = base_data(filters)
	dates = {
		d.name: d.relieving_date
		for d in frappe.get_all(
			"Employee",
			filters={"name": ["in", list({r.employee for r in data})]},
			fields=["name", "relieving_date"],
		)
	}
	for row in data:
		row["relieving_date"] = dates.get(row.employee)
	return columns, data
