# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt

from gicore.gi_assets import utils


class EquipmentRequest(Document):
	def validate(self):
		if not self.company:
			self.company = frappe.db.get_value("Employee", self.employee, "company") or utils.default_company()
		if flt(self.qty) <= 0:
			frappe.throw(_("Quantity must be greater than zero."))
		self.set_manager_user()

	def set_manager_user(self):
		"""Line manager = the user of the employee's `Reports To`. Used by the workflow condition."""
		reports_to = frappe.db.get_value("Employee", self.employee, "reports_to")
		self.manager_user = frappe.db.get_value("Employee", reports_to, "user_id") if reports_to else None
