# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint


class EquipmentModel(Document):
	def validate(self):
		self.model_name = (self.model_name or "").strip()
		if cint(self.default_warranty_months) < 0:
			frappe.throw(_("Default Warranty (months) cannot be negative."))

		before = self.get_doc_before_save()
		if before and before.brand != self.brand and frappe.db.exists("Equipment", {"model": self.name}):
			frappe.throw(_("Brand cannot be changed while Equipment records use this model."))
