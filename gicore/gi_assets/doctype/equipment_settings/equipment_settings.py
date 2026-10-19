# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class EquipmentSettings(Document):
	def validate(self):
		if cint(self.reminder_period_months) < 0:
			frappe.throw(_("Reminder Period (months) cannot be negative."))
		if cint(self.sync_to_asset_movement) and not self.asset_receipt_location:
			frappe.throw(
				_("Asset Receipt Location is required when syncing with Asset Movement (needed for returns).")
			)
