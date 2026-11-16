# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, flt, now_datetime

from gicore.gi_assets import utils

SERIALIZED = "Serialized"
QUANTITY = "Quantity"


class EquipmentHandover(Document):
	"""The single document that moves equipment between store and employees.

	Issue    : store -> employee
	Return   : employee -> store (OK / Damaged / Missing per row)
	Transfer : employee A -> employee B (no store round-trip)

	Submitting writes the Equipment Ledger, updates Equipment status / custodian and,
	if enabled in settings, creates ERPNext Asset Movements for linked Assets.
	"""

	# ------------------------------------------------------------------ validate
	def validate(self):
		if not self.company:
			self.company = frappe.db.get_value("Employee", self.employee, "company") or utils.default_company()
		self.validate_parties()
		self.set_item_details()
		self.validate_items()
		self.set_terms()
		self.validate_request()

	def validate_parties(self):
		if self.handover_type == "Transfer":
			if not self.from_employee:
				frappe.throw(_("From Employee is required for a Transfer."))
			if self.from_employee == self.employee:
				frappe.throw(_("From Employee and To Employee cannot be the same."))
		else:
			self.from_employee = None
			self.from_employee_name = None
			if self.handover_type == "Return":
				self.equipment_request = None

		if self.handover_type in ("Issue", "Transfer"):
			status = frappe.db.get_value("Employee", self.employee, "status")
			if status != "Active":
				frappe.throw(
					_("Equipment can only be issued to an Active employee. {0} is {1}.").format(self.employee, status)
				)

		if not self.site:
			self.site = frappe.db.get_value("Employee", self.employee, "branch") or utils.get_settings().default_site

	def set_item_details(self):
		categories = {}
		for row in self.items:
			if row.equipment:
				eq = frappe.db.get_value(
					"Equipment",
					row.equipment,
					["category", "condition", "serial_no", "equipment_name", "linked_asset"],
					as_dict=True,
				)
				if not eq:
					frappe.throw(_("Row {0}: Equipment {1} does not exist.").format(row.idx, row.equipment))
				if row.category and row.category != eq.category:
					frappe.throw(
						_("Row {0}: {1} belongs to category {2}, not {3}.").format(
							row.idx, row.equipment, eq.category, row.category
						)
					)
				row.category = eq.category
				row.equipment_name = eq.equipment_name
				row.serial_no = eq.serial_no
				row.linked_asset = eq.linked_asset
				if not row.condition_out:
					row.condition_out = eq.condition

			if not row.category:
				frappe.throw(_("Row {0}: select a Category or an Equipment.").format(row.idx))

			if row.category not in categories:
				categories[row.category] = frappe.db.get_value(
					"Equipment Category",
					row.category,
					["tracking_type", "default_accessories", "requires_photo_on_return"],
					as_dict=True,
				)
			cat = categories[row.category]
			row.tracking_type = cat.tracking_type

			if cat.tracking_type == SERIALIZED:
				row.qty = 1
			else:
				row.qty = flt(row.qty)
				if row.qty <= 0:
					frappe.throw(_("Row {0}: Quantity must be greater than zero.").format(row.idx))

			if self.handover_type == "Issue" and not row.accessories and cat.default_accessories:
				row.accessories = cat.default_accessories

	def validate_items(self):
		if not self.items:
			frappe.throw(_("Add at least one item."))

		seen = set()
		for row in self.items:
			if row.equipment:
				if row.equipment in seen:
					frappe.throw(_("Row {0}: {1} is listed more than once.").format(row.idx, row.equipment))
				seen.add(row.equipment)

			if self.handover_type == "Return":
				if not row.return_result:
					row.return_result = "Returned OK"
				if row.return_result == "Damaged":
					row.condition_in = "Damaged"
				elif row.return_result == "Returned OK" and row.condition_in == "Damaged":
					frappe.throw(
						_("Row {0}: condition is Damaged but the result is Returned OK. Set the result to Damaged.").format(
							row.idx
						)
					)
			else:
				row.return_result = None
				row.condition_in = None

	def set_terms(self):
		if not self.terms_template:
			self.terms_template = utils.get_settings().default_terms_template
		if self.terms_template:
			self.terms = frappe.db.get_value("Terms and Conditions", self.terms_template, "terms")

	def validate_request(self):
		if not self.equipment_request:
			return
		if self.handover_type != "Issue":
			self.equipment_request = None
			return
		req = frappe.db.get_value(
			"Equipment Request", self.equipment_request, ["employee", "docstatus"], as_dict=True
		)
		if req.employee != self.employee:
			frappe.throw(_("Equipment Request {0} belongs to {1}.").format(self.equipment_request, req.employee))

	# ------------------------------------------------------------------ submit
	def before_submit(self):
		settings = utils.get_settings()
		if cint(settings.require_signature) and not self.employee_signature:
			frappe.throw(_("The employee signature is required before submitting."))

		if self.equipment_request:
			state = frappe.db.get_value("Equipment Request", self.equipment_request, "workflow_state")
			if state != "Approved":
				frappe.throw(
					_("Equipment Request {0} is {1}. Only Approved requests can be fulfilled.").format(
						self.equipment_request, state
					)
				)

		categories = {}
		for row in self.items:
			if row.tracking_type == SERIALIZED and not row.equipment:
				frappe.throw(_("Row {0}: select the Equipment (serial number) for {1}.").format(row.idx, row.category))

			if self.handover_type == "Return":
				if row.return_result != "Missing" and not row.condition_in:
					frappe.throw(_("Row {0}: Condition on return is required.").format(row.idx))
				if row.category not in categories:
					categories[row.category] = cint(
						frappe.db.get_value("Equipment Category", row.category, "requires_photo_on_return")
					)
				if categories[row.category] and row.return_result != "Missing" and not row.photo:
					frappe.throw(
						_("Row {0}: a photo is required when returning {1}.").format(row.idx, row.category)
					)
			elif not row.condition_out:
				frappe.throw(_("Row {0}: Condition is required.").format(row.idx))

		self.acknowledged_on = now_datetime()

	def on_submit(self):
		handler = {
			"Issue": self._issue_row,
			"Return": self._return_row,
			"Transfer": self._transfer_row,
		}[self.handover_type]
		for row in self.items:
			handler(row)

		self._mark_request(fulfilled=True)
		self._notify()

	# ------------------------------------------------------------------ cancel
	def on_cancel(self):
		for row in self.items:
			self._reverse_row(row)

		utils.reverse_ledger_entries(self.doctype, self.name)
		self._cancel_asset_movements()
		self._mark_request(fulfilled=False)

	# ------------------------------------------------------------------ Issue
	def _issue_row(self, row):
		if row.tracking_type == SERIALIZED:
			eq = self._lock(row.equipment)
			if eq.status != "In Stock":
				frappe.throw(
					_("Row {0}: {1} is not In Stock (current status: {2}).").format(row.idx, eq.name, eq.status)
				)
			self._set_equipment(
				eq, status="Issued", current_custodian=self.employee, condition=row.condition_out or eq.condition
			)
			self._ledger("Issue", row, stock=-1, custody=1)
		else:
			self._check_stock(row)
			self._ledger("Issue", row, stock=-flt(row.qty), custody=flt(row.qty))

		self._sync_asset(row, "Issue")

	def _check_stock(self, row):
		if cint(utils.get_settings().allow_negative_stock):
			return
		balance = utils.get_stock_balance(row.category, self.site, self.company)
		if balance < flt(row.qty):
			frappe.throw(
				_("Row {0}: only {1} of {2} available at {3}, you are issuing {4}.").format(
					row.idx, flt(balance), row.category, self.site or _("all sites"), flt(row.qty)
				)
			)

	# ------------------------------------------------------------------ Return
	def _return_row(self, row):
		result = row.return_result or "Returned OK"

		if row.tracking_type == SERIALIZED:
			eq = self._lock(row.equipment)
			if eq.status != "Issued" or eq.current_custodian != self.employee:
				frappe.throw(
					_("Row {0}: {1} is not currently held by {2}.").format(row.idx, eq.name, self.employee)
				)
			new_status = {"Returned OK": "In Stock", "Damaged": "In Repair", "Missing": "Lost"}[result]
			values = {"status": new_status, "current_custodian": None}
			if result != "Missing":
				values["condition"] = row.condition_in
			self._set_equipment(eq, **values)
			self._ledger("Return", row, stock=1 if result == "Returned OK" else 0, custody=-1, remarks=result)
		else:
			held = utils.get_custody_balance(row.category, self.employee)
			if held < flt(row.qty):
				frappe.throw(
					_("Row {0}: {1} only holds {2} of {3}.").format(row.idx, self.employee, flt(held), row.category)
				)
			self._ledger(
				"Return",
				row,
				stock=flt(row.qty) if result == "Returned OK" else 0,
				custody=-flt(row.qty),
				remarks=result,
			)

		if result in ("Damaged", "Missing"):
			self._create_incident(row, result)
		if result != "Missing":
			self._sync_asset(row, "Return")

	# ------------------------------------------------------------------ Transfer
	def _transfer_row(self, row):
		if row.tracking_type == SERIALIZED:
			eq = self._lock(row.equipment)
			if eq.status != "Issued" or eq.current_custodian != self.from_employee:
				frappe.throw(
					_("Row {0}: {1} is not currently held by {2}.").format(row.idx, eq.name, self.from_employee)
				)
			self._set_equipment(eq, current_custodian=self.employee)
		else:
			held = utils.get_custody_balance(row.category, self.from_employee)
			if held < flt(row.qty):
				frappe.throw(
					_("Row {0}: {1} only holds {2} of {3}.").format(
						row.idx, self.from_employee, flt(held), row.category
					)
				)

		self._ledger("Transfer Out", row, custody=-flt(row.qty), employee=self.from_employee)
		self._ledger("Transfer In", row, custody=flt(row.qty), employee=self.employee)
		self._sync_asset(row, "Transfer")

	# ------------------------------------------------------------------ cancel helpers
	def _reverse_row(self, row):
		serialized = row.tracking_type == SERIALIZED
		eq = self._lock(row.equipment) if serialized else None

		if self.handover_type == "Issue":
			if serialized:
				if eq.status != "Issued" or eq.current_custodian != self.employee:
					self._cannot_cancel(row)
				self._set_equipment(eq, status="In Stock", current_custodian=None)
			elif utils.get_custody_balance(row.category, self.employee) < flt(row.qty):
				self._cannot_cancel(row)

		elif self.handover_type == "Return":
			result = row.return_result or "Returned OK"
			if serialized:
				expected = {"Returned OK": "In Stock", "Damaged": "In Repair", "Missing": "Lost"}[result]
				if eq.status != expected or eq.current_custodian:
					self._cannot_cancel(row)
				self._set_equipment(eq, status="Issued", current_custodian=self.employee)
			elif result == "Returned OK" and not cint(utils.get_settings().allow_negative_stock):
				if utils.get_stock_balance(row.category, self.site, self.company) < flt(row.qty):
					self._cannot_cancel(row)
			self._delete_incident(row)

		else:  # Transfer
			if serialized:
				if eq.status != "Issued" or eq.current_custodian != self.employee:
					self._cannot_cancel(row)
				self._set_equipment(eq, current_custodian=self.from_employee)
			elif utils.get_custody_balance(row.category, self.employee) < flt(row.qty):
				self._cannot_cancel(row)

	def _cannot_cancel(self, row):
		frappe.throw(
			_(
				"Row {0}: cannot cancel because a later movement exists for {1}. "
				"Cancel the later documents first."
			).format(row.idx, row.equipment or row.category)
		)

	def _delete_incident(self, row):
		filters = {"handover": self.name, "handover_item": row.name}
		for name in frappe.get_all("Equipment Incident", filters=filters, pluck="name"):
			status, applied = frappe.db.get_value(
				"Equipment Incident", name, ["status", "resolution_applied"]
			)
			if status != "Open" or cint(applied):
				frappe.throw(
					_("Incident {0} from this return is already resolved. Reopen or reverse it first.").format(name)
				)
			frappe.flags.in_handover_cancel = True
			try:
				frappe.delete_doc("Equipment Incident", name, force=1, ignore_permissions=True)
			finally:
				frappe.flags.in_handover_cancel = False

	# ------------------------------------------------------------------ shared helpers
	def _lock(self, equipment):
		return frappe.get_doc("Equipment", equipment, for_update=True)

	def _set_equipment(self, eq, **values):
		eq.flags.from_custody = True
		eq.flags.ignore_permissions = True
		eq.update(values)
		eq.save()

	def _ledger(self, movement_type, row, stock=0, custody=0, employee=None, remarks=None):
		return utils.post_ledger(
			movement_type=movement_type,
			category=row.category,
			qty=flt(row.qty),
			stock_effect=stock,
			custody_effect=custody,
			employee=employee or self.employee,
			equipment=row.equipment,
			site=self.site,
			company=self.company,
			condition=row.condition_in if self.handover_type == "Return" else row.condition_out,
			reference_doctype=self.doctype,
			reference_name=self.name,
			reference_row=row.name,
			remarks=remarks,
		)

	def _create_incident(self, row, result):
		incident_type = "Damage" if result == "Damaged" else "Loss"

		# re-use a damage report the employee already filed for this unit
		if incident_type == "Damage" and row.equipment:
			existing = frappe.db.get_value(
				"Equipment Incident",
				{
					"equipment": row.equipment,
					"employee": self.employee,
					"incident_type": "Damage",
					"status": "Open",
					"handover": ["is", "not set"],
				},
				"name",
			)
			if existing:
				frappe.db.set_value(
					"Equipment Incident", existing, {"handover": self.name, "handover_item": row.name}
				)
				return

		incident = frappe.get_doc(
			{
				"doctype": "Equipment Incident",
				"equipment": row.equipment,
				"category": row.category,
				"qty": flt(row.qty),
				"employee": self.employee,
				"incident_date": self.posting_date,
				"incident_type": incident_type,
				"description": row.remarks or _("Reported on return ({0})").format(self.name),
				"attachment": row.photo,
				"handover": self.name,
				"handover_item": row.name,
				"resolution": "Pending",
				"status": "Open",
				"company": self.company,
			}
		)
		incident.flags.ignore_permissions = True
		incident.insert()

	# ------------------------------------------------------------------ request / notifications
	def _mark_request(self, fulfilled):
		if self.handover_type != "Issue" or not self.equipment_request:
			return
		frappe.db.set_value(
			"Equipment Request",
			self.equipment_request,
			"workflow_state",
			"Fulfilled" if fulfilled else "Approved",
		)

	def _notify(self):
		if frappe.flags.in_demo_data or not cint(utils.get_settings().notify_employee):
			return

		subjects = {
			"Issue": _("Equipment issued to you"),
			"Return": _("Equipment return recorded"),
			"Transfer": _("Equipment transferred to you"),
		}
		recipients = {self.employee: subjects[self.handover_type]}
		if self.handover_type == "Transfer" and self.from_employee:
			recipients[self.from_employee] = _("Equipment transferred from you")

		for employee, subject in recipients.items():
			email = utils.get_employee_email(employee)
			if not email:
				continue
			try:
				frappe.sendmail(
					recipients=[email],
					subject=f"{subject} - {self.name}",
					message=utils.handover_items_html(self.items),
					reference_doctype=self.doctype,
					reference_name=self.name,
					delayed=True,
				)
			except Exception:
				frappe.log_error(title="Equipment handover notification failed")

	# ------------------------------------------------------------------ optional ERPNext Asset sync
	def _sync_asset(self, row, action):
		"""Only when 'Sync to Asset Movement' is on in settings AND the equipment has a linked Asset."""
		settings = utils.get_settings()
		if not (cint(settings.sync_to_asset_movement) and row.linked_asset):
			return

		location = settings.asset_receipt_location
		if action == "Issue":
			names = [self._asset_movement("Issue", row.linked_asset, to_employee=self.employee)]
		elif action == "Return":
			names = [
				self._asset_movement(
					"Receipt", row.linked_asset, from_employee=self.employee, target_location=location
				)
			]
		else:  # Transfer: Asset Movement cannot go employee -> employee, so Receipt then Issue
			names = [
				self._asset_movement(
					"Receipt", row.linked_asset, from_employee=self.from_employee, target_location=location
				),
				self._asset_movement("Issue", row.linked_asset, to_employee=self.employee),
			]

		row.asset_movements = ", ".join(names)
		frappe.db.set_value("Equipment Handover Item", row.name, "asset_movements", row.asset_movements)

	def _asset_movement(self, purpose, asset, from_employee=None, to_employee=None, target_location=None):
		movement = frappe.new_doc("Asset Movement")
		movement.company = self.company
		movement.purpose = purpose
		movement.transaction_date = now_datetime()
		movement.append(
			"assets",
			{
				"asset": asset,
				"from_employee": from_employee,
				"to_employee": to_employee,
				"target_location": target_location,
			},
		)
		movement.flags.ignore_permissions = True
		movement.insert()
		movement.submit()
		return movement.name

	def _cancel_asset_movements(self):
		for row in self.items:
			names = [n.strip() for n in (row.asset_movements or "").split(",") if n.strip()]
			for name in reversed(names):
				movement = frappe.get_doc("Asset Movement", name)
				if movement.docstatus == 1:
					movement.flags.ignore_permissions = True
					movement.cancel()


# ---------------------------------------------------------------------------
# Form helpers (called from the client script)
# ---------------------------------------------------------------------------
@frappe.whitelist()
def get_kit_items(employee):
	"""Rows of the Equipment Kit that matches the employee's designation (first) or department."""
	frappe.has_permission("Equipment Handover", "create", throw=True)

	emp = frappe.db.get_value("Employee", employee, ["designation", "department"], as_dict=True)
	if not emp:
		frappe.throw(_("Employee {0} not found.").format(employee))

	kit = None
	if emp.designation:
		kit = frappe.db.get_value("Equipment Kit", {"enabled": 1, "designation": emp.designation}, "name")
	if not kit and emp.department:
		kit = frappe.db.get_value("Equipment Kit", {"enabled": 1, "department": emp.department}, "name")
	if not kit:
		frappe.throw(_("No enabled Equipment Kit matches this employee's designation or department."))

	rows = []
	for item in frappe.get_all(
		"Equipment Kit Item", filters={"parent": kit}, fields=["category", "qty"], order_by="idx"
	):
		tracking_type = frappe.db.get_value("Equipment Category", item.category, "tracking_type")
		if tracking_type == SERIALIZED:
			# one row per unit so IT can pick the serial number for each
			rows += [{"category": item.category, "qty": 1} for _i in range(max(int(flt(item.qty)), 1))]
		else:
			rows.append({"category": item.category, "qty": flt(item.qty)})
	return rows


@frappe.whitelist()
def get_employee_custody_items(employee):
	"""Everything the employee currently holds, as handover rows (for Return / Transfer)."""
	frappe.has_permission("Equipment Handover", "create", throw=True)

	custody = utils.get_employee_custody(employee)
	rows = [
		{"category": d.category, "equipment": d.name, "qty": 1, "condition_out": d.condition}
		for d in custody.serialized
	]
	rows += [{"category": d.category, "qty": flt(d.qty)} for d in custody.quantity]
	return rows
