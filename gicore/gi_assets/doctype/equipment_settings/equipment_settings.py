# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class EquipmentSettings(Document):
	def validate(self):
		# demo tracking is written only by demo_data.py; a form opened before the demo ran must not wipe it
		for fieldname in ("demo_data_created", "demo_data_log"):
			self.set(fieldname, frappe.db.get_single_value("Equipment Settings", fieldname))
		if cint(self.reminder_period_months) < 0:
			frappe.throw(_("Reminder Period (months) cannot be negative."))
		if cint(self.sync_to_asset_movement) and not self.asset_receipt_location:
			frappe.throw(
				_("Asset Receipt Location is required when syncing with Asset Movement (needed for returns).")
			)
