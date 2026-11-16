# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document


class EquipmentKit(Document):
	def validate(self):
		if not (self.designation or self.department):
			frappe.throw(_("Set a Designation or a Department for this kit."))
		if not self.items:
			frappe.throw(_("Add at least one item to the kit."))
		seen = set()
		for row in self.items:
			if row.category in seen:
				frappe.throw(_("Row {0}: category {1} is repeated. Increase the quantity instead.").format(row.idx, row.category))
			seen.add(row.category)
