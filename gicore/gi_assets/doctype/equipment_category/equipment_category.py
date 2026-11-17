# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document


class EquipmentCategory(Document):
	def validate(self):
		if self.parent_category and self.parent_category == self.name:
			frappe.throw(_("A category cannot be its own parent."))

		before = self.get_doc_before_save()
		if before and before.tracking_type != self.tracking_type:
			if frappe.db.exists("Equipment Ledger", {"category": self.name}):
				frappe.throw(
					_("Tracking Type cannot be changed because this category already has movements.")
				)
