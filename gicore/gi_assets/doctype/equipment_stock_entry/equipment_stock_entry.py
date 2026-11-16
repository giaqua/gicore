# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt

from gicore.gi_assets import utils


class EquipmentStockEntry(Document):
	"""Receive or adjust stock of quantity-tracked items (mouse, keyboard, cables ...)."""

	def validate(self):
		if not self.company:
			self.company = utils.default_company()
		if not self.site:
			self.site = utils.get_settings().default_site

		tracking_type = frappe.db.get_value("Equipment Category", self.category, "tracking_type")
		if tracking_type != "Quantity":
			frappe.throw(
				_(
					"Stock entries are only for quantity-tracked categories. "
					"Serialized items are added as Equipment records."
				)
			)

		qty = flt(self.qty)
		if not qty:
			frappe.throw(_("Quantity cannot be zero."))
		if self.entry_type == "Receipt" and qty < 0:
			frappe.throw(_("A Receipt must have a positive quantity. Use Adjustment to reduce stock."))

		if qty < 0:
			self.check_balance(abs(qty))

	def check_balance(self, needed):
		if cint(utils.get_settings().allow_negative_stock):
			return
		balance = utils.get_stock_balance(self.category, self.site, self.company)
		if balance < needed:
			frappe.throw(
				_("Only {0} of {1} in stock at {2}, cannot reduce by {3}.").format(
					flt(balance), self.category, self.site or _("all sites"), flt(needed)
				)
			)

	def on_submit(self):
		qty = flt(self.qty)
		utils.post_ledger(
			movement_type="Stock In" if self.entry_type == "Receipt" else "Adjustment",
			category=self.category,
			qty=abs(qty),
			stock_effect=qty,
			site=self.site,
			company=self.company,
			reference_doctype=self.doctype,
			reference_name=self.name,
			remarks=self.remarks or self.reference,
		)

	def on_cancel(self):
		qty = flt(self.qty)
		if qty > 0:
			# cancelling a receipt removes units, make sure they are still in the store
			self.check_balance(qty)
		utils.reverse_ledger_entries(self.doctype, self.name)
