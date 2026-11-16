# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document

from gicore.gi_assets import utils


class Equipment(Document):
	"""One record per serialized unit (laptop, phone, monitor ...).

	`status` and `current_custodian` are system fields: after creation they can only be
	changed by a submitted Equipment Handover / Incident (flags.from_custody).
	"""

	def validate(self):
		if not self.company:
			self.company = utils.default_company()
		self.validate_category()
		self.validate_unique_serial()
		self.validate_linked_asset()
		self.validate_system_fields()
		self.barcode = self.name
		self.custodian_name = (
			frappe.db.get_value("Employee", self.current_custodian, "employee_name")
			if self.current_custodian
			else None
		)

	def validate_category(self):
		tracking_type = frappe.db.get_value("Equipment Category", self.category, "tracking_type")
		if tracking_type != "Serialized":
			frappe.throw(
				_(
					"Category {0} is tracked by quantity. Only Serialized categories have Equipment records; "
					"use an Equipment Stock Entry for quantity items."
				).format(frappe.bold(self.category))
			)
		before = self.get_doc_before_save()
		if before and before.category != self.category:
			frappe.throw(_("Category cannot be changed after the equipment is created."))

	def validate_unique_serial(self):
		if not self.serial_no:
			return
		duplicate = frappe.db.exists(
			"Equipment",
			{"serial_no": self.serial_no, "category": self.category, "name": ["!=", self.name]},
		)
		if duplicate:
			frappe.throw(
				_("Serial No {0} already exists in category {1} ({2}).").format(
					frappe.bold(self.serial_no), self.category, duplicate
				)
			)

	def validate_linked_asset(self):
		if not self.linked_asset:
			return
		other = frappe.db.exists("Equipment", {"linked_asset": self.linked_asset, "name": ["!=", self.name]})
		if other:
			frappe.throw(_("Asset {0} is already linked to {1}.").format(self.linked_asset, other))

	def validate_system_fields(self):
		if self.is_new():
			# Opening balance: an existing laptop can be created already Issued to someone.
			if self.current_custodian:
				self.status = "Issued"
			if self.status == "Issued" and not self.current_custodian:
				frappe.throw(_("Current Custodian is required when the opening status is Issued."))
			if self.status != "Issued" and self.current_custodian:
				frappe.throw(_("Only Issued equipment can have a custodian."))
			return

		before = self.get_doc_before_save()
		if not before or self.flags.from_custody:
			return
		if (before.status != self.status) or ((before.current_custodian or None) != (self.current_custodian or None)):
			frappe.throw(
				_(
					"Status and Current Custodian are controlled by Equipment Handover and Equipment Incident. "
					"Create a handover instead of editing them."
				)
			)

	def after_insert(self):
		# every unit is born into the ledger (Stock In); opening custody posts a matching Issue
		in_store = 1 if self.status in ("In Stock", "Issued") else 0
		utils.post_ledger(
			movement_type="Stock In",
			category=self.category,
			qty=1,
			stock_effect=in_store,
			equipment=self.name,
			site=self.site,
			company=self.company,
			condition=self.condition,
			reference_doctype=self.doctype,
			reference_name=self.name,
			remarks=_("Equipment created ({0})").format(self.status),
		)
		if self.status == "Issued":
			utils.post_ledger(
				movement_type="Issue",
				category=self.category,
				qty=1,
				stock_effect=-1,
				custody_effect=1,
				employee=self.current_custodian,
				equipment=self.name,
				site=self.site,
				company=self.company,
				condition=self.condition,
				reference_doctype=self.doctype,
				reference_name=self.name,
				remarks=_("Opening custody"),
			)
