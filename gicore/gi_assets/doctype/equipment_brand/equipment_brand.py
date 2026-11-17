# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

from frappe.model.document import Document


class EquipmentBrand(Document):
	def validate(self):
		self.brand_name = (self.brand_name or "").strip()
