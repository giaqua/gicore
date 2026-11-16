# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, getdate

from gicore.gi_assets import utils

LOSS_TYPES = ("Loss", "Theft")


class EquipmentIncident(Document):
	"""Damage / loss / theft of equipment, with optional salary deduction."""

	def validate(self):
		if not self.company:
			self.company = utils.default_company()
		self.set_category()
		self.validate_liability()
		self.validate_resolution()

	def set_category(self):
		if self.equipment:
			category = frappe.db.get_value("Equipment", self.equipment, "category")
			if self.category and self.category != category:
				frappe.throw(_("Equipment {0} does not belong to category {1}.").format(self.equipment, self.category))
			self.category = category
			self.qty = 1
		if not self.category:
			frappe.throw(_("Select an Equipment or a Category."))
		if not self.equipment and flt(self.qty) <= 0:
			frappe.throw(_("Quantity must be greater than zero."))

	def validate_liability(self):
		if cint(self.employee_liability):
			if not self.employee:
				frappe.throw(_("Employee is required when the employee is liable."))
			if flt(self.deduction_amount) <= 0:
				frappe.throw(_("Enter the deduction amount."))
		else:
			self.deduction_amount = 0

	def validate_resolution(self):
		if self.status != "Resolved":
			return
		if self.resolution in (None, "", "Pending"):
			frappe.throw(_("Choose a Resolution before marking the incident as Resolved."))
		if self.incident_type == "Damage" and self.resolution == "Written Off":
			frappe.throw(_("Damaged equipment is either Repaired or Scrapped."))
		if self.incident_type in LOSS_TYPES and self.resolution in ("Repaired", "Scrapped"):
			frappe.throw(_("Lost or stolen equipment can only be Written Off."))

	# ------------------------------------------------------------------ side effects
	def after_insert(self):
		"""A loss/theft reported directly (not via a return handover) ends the custody now."""
		if self.handover or self.incident_type not in LOSS_TYPES:
			return
		self.apply_loss()

	def on_update(self):
		if self.status == "Resolved" and not cint(self.resolution_applied):
			self.apply_resolution()

	def apply_loss(self):
		common = dict(
			movement_type="Written Off",
			category=self.category,
			qty=flt(self.qty),
			company=self.company,
			reference_doctype=self.doctype,
			reference_name=self.name,
			remarks=_("{0} reported").format(self.incident_type),
		)
		if self.equipment:
			eq = frappe.get_doc("Equipment", self.equipment, for_update=True)
			if eq.status == "Issued":
				if self.employee and eq.current_custodian != self.employee:
					frappe.throw(
						_("{0} is held by {1}, not {2}.").format(eq.name, eq.current_custodian, self.employee)
					)
				utils.post_ledger(
					stock_effect=0, custody_effect=-1, employee=eq.current_custodian, equipment=eq.name, site=eq.site, **common
				)
			elif eq.status == "In Stock":
				utils.post_ledger(stock_effect=-1, equipment=eq.name, site=eq.site, **common)
			else:
				frappe.throw(_("{0} is {1} and cannot be reported lost.").format(eq.name, eq.status))
			eq.flags.from_custody = True
			eq.flags.ignore_permissions = True
			eq.update({"status": "Lost", "current_custodian": None})
			eq.save()
		else:
			if self.employee:
				held = utils.get_custody_balance(self.category, self.employee)
				if held < flt(self.qty):
					frappe.throw(
						_("{0} only holds {1} of {2}.").format(self.employee, held, self.category)
					)
				utils.post_ledger(stock_effect=0, custody_effect=-flt(self.qty), employee=self.employee, **common)
			else:
				utils.post_ledger(stock_effect=-flt(self.qty), **common)
		self.db_set("loss_applied", 1)

	def apply_resolution(self):
		if self.resolution == "Repaired":
			self._repaired()
		elif self.resolution == "Scrapped":
			self._scrapped()
		# "Written Off": the stock effect was already posted when the loss was recorded
		self.db_set({"resolution_applied": 1, "resolved_on": getdate()})

	def _repaired(self):
		if self.equipment:
			eq = frappe.get_doc("Equipment", self.equipment, for_update=True)
			if eq.status != "In Repair":
				frappe.throw(_("{0} must be In Repair (return it first). Current status: {1}.").format(eq.name, eq.status))
			eq.flags.from_custody = True
			eq.flags.ignore_permissions = True
			eq.update({"status": "In Stock", "condition": "Good"})
			eq.save()
			site = eq.site
		else:
			site = None
		utils.post_ledger(
			movement_type="Repair Completed",
			category=self.category,
			qty=flt(self.qty),
			stock_effect=flt(self.qty),
			equipment=self.equipment,
			site=site,
			company=self.company,
			reference_doctype=self.doctype,
			reference_name=self.name,
		)

	def _scrapped(self):
		stock_effect = 0
		site = None
		if self.equipment:
			eq = frappe.get_doc("Equipment", self.equipment, for_update=True)
			if eq.status not in ("In Repair", "In Stock"):
				frappe.throw(
					_("{0} must be In Repair or In Stock to be scrapped. Current status: {1}.").format(eq.name, eq.status)
				)
			stock_effect = -1 if eq.status == "In Stock" else 0
			site = eq.site
			eq.flags.from_custody = True
			eq.flags.ignore_permissions = True
			eq.update({"status": "Scrapped"})
			eq.save()
		utils.post_ledger(
			movement_type="Scrapped",
			category=self.category,
			qty=flt(self.qty),
			stock_effect=stock_effect,
			equipment=self.equipment,
			site=site,
			company=self.company,
			reference_doctype=self.doctype,
			reference_name=self.name,
		)

	def on_trash(self):
		if frappe.flags.in_handover_cancel or frappe.flags.in_demo_cleanup:
			return
		if cint(self.loss_applied) or cint(self.resolution_applied):
			frappe.throw(_("This incident already changed stock or custody and cannot be deleted."))


@frappe.whitelist()
def create_additional_salary(incident):
	"""Draft an Additional Salary (deduction) for HR to review and submit."""
	doc = frappe.get_doc("Equipment Incident", incident)
	doc.check_permission("write")

	if not cint(doc.employee_liability) or flt(doc.deduction_amount) <= 0:
		frappe.throw(_("Mark the employee as liable and enter a deduction amount first."))
	if doc.additional_salary:
		frappe.throw(_("Additional Salary {0} already exists for this incident.").format(doc.additional_salary))

	component = utils.get_settings().deduction_salary_component
	if not component:
		frappe.throw(_("Set 'Deduction Salary Component' in Equipment Settings first."))

	additional_salary = frappe.new_doc("Additional Salary")
	additional_salary.update(
		{
			"employee": doc.employee,
			"company": doc.company or frappe.db.get_value("Employee", doc.employee, "company"),
			"salary_component": component,
			"amount": doc.deduction_amount,
			"payroll_date": getdate(),
			"overwrite_salary_structure_amount": 1,
			"ref_doctype": doc.doctype,
			"ref_docname": doc.name,
		}
	)
	try:
		additional_salary.insert()
	except frappe.PermissionError:
		frappe.throw(_("You do not have permission to create an Additional Salary. Ask HR to create it."))

	doc.db_set("additional_salary", additional_salary.name)
	return additional_salary.name
