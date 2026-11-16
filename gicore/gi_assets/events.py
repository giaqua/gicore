# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT
"""doc_events: block employee exit / clearance while equipment is still in custody."""

import frappe
from frappe import _
from frappe.utils import cint

from gicore.gi_assets import utils


def check_clearance(employee):
	settings = utils.get_settings()
	if not cint(settings.block_separation_if_custody_open):
		return

	custody = utils.get_employee_custody(employee)
	if not (custody.serialized or custody.quantity):
		return

	frappe.throw(
		_("{0} still holds company equipment. Create an Equipment Handover (Return) first.").format(
			frappe.bold(employee)
		)
		+ "<br><br>"
		+ utils.custody_items_html(custody),
		title=_("Equipment Custody Not Cleared"),
	)


def employee_validate(doc, method=None):
	"""Block setting an Employee to Left while custody is open."""
	if doc.is_new() or doc.status != "Left":
		return
	before = doc.get_doc_before_save()
	if before and before.status == "Left":
		return
	check_clearance(doc.name)


def separation_before_submit(doc, method=None):
	"""Employee Separation / Full and Final Statement."""
	if doc.get("employee"):
		check_clearance(doc.employee)
