# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT
"""Scheduled jobs."""

import frappe
from frappe import _
from frappe.utils import add_days, add_months, cint, getdate, nowdate

from gicore.gi_assets import utils


def daily():
	send_custody_confirmations()
	# manager digests only once a week (Monday) to avoid noise
	if getdate().weekday() == 0:
		send_manager_digest()


def send_custody_confirmations():
	"""Every N months, email each employee the list of equipment recorded against them."""
	settings = utils.get_settings()
	months = cint(settings.reminder_period_months)
	if not months:
		return
	if settings.last_reminder_on and add_months(settings.last_reminder_on, months) > getdate():
		return

	employees = set(
		frappe.get_all(
			"Equipment",
			filters={"status": "Issued", "current_custodian": ["is", "set"]},
			pluck="current_custodian",
		)
	)
	qty_holders = frappe.db.sql(
		"""select distinct l.employee
		from `tabEquipment Ledger` l
		inner join `tabEquipment Category` c on c.name = l.category
		where c.tracking_type = 'Quantity' and l.employee is not null
		group by l.employee, l.category
		having sum(l.custody_effect) > 0""",
		pluck=True,
	)
	employees.update(qty_holders)

	for employee in employees:
		email = utils.get_employee_email(employee)
		if not email:
			continue
		custody = utils.get_employee_custody(employee)
		if not (custody.serialized or custody.quantity):
			continue
		try:
			frappe.sendmail(
				recipients=[email],
				subject=_("Please confirm the equipment in your custody"),
				message=_(
					"This is a periodic confirmation. Our records show the following equipment in your custody. "
					"Please contact IT if anything is wrong."
				)
				+ "<br><br>"
				+ utils.custody_items_html(custody),
				reference_doctype="Employee",
				reference_name=employee,
				delayed=True,
			)
		except Exception:
			frappe.log_error(title="Equipment custody confirmation email failed")

	frappe.db.set_single_value("Equipment Settings", "last_reminder_on", nowdate())


def send_manager_digest():
	"""Warranty expiring soon + employees who left but still hold equipment."""
	settings = utils.get_settings()
	days = cint(settings.warranty_alert_days) or 30

	expiring = frappe.get_all(
		"Equipment",
		filters={
			"warranty_expiry": ["between", [nowdate(), add_days(nowdate(), days)]],
			"status": ["not in", ["Scrapped", "Lost"]],
		},
		fields=["name", "equipment_name", "serial_no", "warranty_expiry"],
		order_by="warranty_expiry",
	)

	left = frappe.db.sql(
		"""select distinct eq.current_custodian as employee, e.employee_name
		from `tabEquipment` eq
		inner join `tabEmployee` e on e.name = eq.current_custodian
		where eq.status = 'Issued' and e.status = 'Left'""",
		as_dict=True,
	)

	if not expiring and not left:
		return

	recipients = _users_with_role("Equipment Manager")
	if not recipients:
		return

	parts = []
	if expiring:
		parts.append("<b>" + _("Warranty expiring within {0} days").format(days) + "</b><ul>")
		parts += [
			f"<li>{frappe.utils.escape_html(d.equipment_name or d.name)} "
			f"({frappe.utils.escape_html(d.serial_no or '-')}) - {d.warranty_expiry}</li>"
			for d in expiring
		]
		parts.append("</ul>")
	if left:
		parts.append("<b>" + _("Employees who left but still hold equipment") + "</b><ul>")
		parts += [
			f"<li>{frappe.utils.escape_html(d.employee_name or d.employee)} ({d.employee})</li>" for d in left
		]
		parts.append("</ul>")

	try:
		frappe.sendmail(
			recipients=recipients,
			subject=_("Equipment custody weekly digest"),
			message="".join(parts),
			delayed=True,
		)
	except Exception:
		frappe.log_error(title="Equipment custody digest email failed")


def _users_with_role(role):
	users = frappe.get_all("Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")
	if not users:
		return []
	return frappe.get_all(
		"User",
		filters={"name": ["in", users], "enabled": 1, "user_type": "System User"},
		pluck="email",
	)
