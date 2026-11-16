# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document


class EquipmentLedger(Document):
	"""Append-only audit trail. Rows are written by utils.post_ledger() only."""

	def validate(self):
		if not self.flags.from_controller:
			frappe.throw(_("Equipment Ledger entries are created automatically and cannot be added manually."))
		if not self.is_new():
			frappe.throw(_("Equipment Ledger entries cannot be modified."))

	def on_trash(self):
		flags = frappe.flags
		if flags.in_install or flags.in_uninstall or flags.in_migrate or flags.in_test:
			return
		frappe.throw(_("Equipment Ledger entries cannot be deleted. Cancel the source document instead."))
