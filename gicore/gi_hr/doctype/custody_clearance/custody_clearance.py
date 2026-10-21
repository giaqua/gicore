import frappe
from frappe import _
from frappe.desk.form import assign_to
from frappe.model.document import Document
from frappe.utils import cint, flt, get_fullname, getdate, now_datetime

DOCTYPE = "Custody Clearance"
SETTINGS = "Custody Clearance Settings"

# Overall statuses in which departments (and the employee) are still acting
ACTIVE_STATES = ("In Clearance", "On Hold", "Pending Employee Acknowledgement")
HR_ROLES = {"System Manager", "HR Manager", "HR User"}


class CustodyClearance(Document):
	# ------------------------------------------------------------------ hooks
	def before_insert(self):
		if not self.clearance_departments:
			self.populate_departments()

	def validate(self):
		self.set_employee_details()
		self.validate_dates()
		self.validate_duplicate_clearance()
		self.block_manual_changes()
		self.validate_rows()
		self.set_overall_status()
		self.set_total_amount_due()

	def before_submit(self):
		if not self.employee_acknowledgement or self.overall_status != "Completed":
			frappe.throw(
				_("A Custody Clearance can only be submitted after the employee acknowledges it."),
				title=_("Employee Acknowledgement Required"),
			)
		if any(row.status != "Cleared" for row in self.clearance_departments):
			frappe.throw(_("All departments must be Cleared before this document can be submitted."))

	def on_update(self):
		self.sync_assignments()

	def on_submit(self):
		self.sync_assignments()

	def before_cancel(self):
		self.overall_status = "Cancelled"

	def on_cancel(self):
		self.db_set("overall_status", "Cancelled", update_modified=False)
		self.sync_assignments()

	# ------------------------------------------------------------- validation
	def set_employee_details(self):
		if not self.employee:
			return
		emp = frappe.db.get_value(
			"Employee",
			self.employee,
			["employee_name", "department", "designation", "company", "user_id"],
			as_dict=True,
		)
		if not emp:
			frappe.throw(_("Employee {0} was not found").format(self.employee))
		self.employee_name = emp.employee_name
		self.department = emp.department
		self.designation = emp.designation
		self.company = emp.company
		self.user_id = emp.user_id

	def validate_dates(self):
		if self.last_working_day and getdate(self.last_working_day) < getdate(self.request_date):
			frappe.throw(_("Last Working Day cannot be before Request Date"))

	def validate_duplicate_clearance(self):
		existing = frappe.db.get_value(
			DOCTYPE,
			{
				"employee": self.employee,
				"docstatus": ["<", 2],
				"overall_status": ["not in", ["Completed", "Cancelled"]],
				"name": ["!=", self.name or ""],
			},
			"name",
		)
		if existing:
			frappe.throw(
				_("Employee {0} already has an open Custody Clearance: {1}").format(
					frappe.bold(self.employee), frappe.get_desk_link(DOCTYPE, existing)
				)
			)

	def validate_rows(self):
		seen = set()
		for row in self.clearance_departments:
			if row.department in seen:
				frappe.throw(
					_("Row {0}: Department {1} is listed more than once").format(
						row.idx, frappe.bold(row.department)
					)
				)
			seen.add(row.department)

			if self.user_id and self.user_id in (row.approver, row.alternate_approver):
				frappe.throw(
					_(
						"Row {0}: The employee cannot approve their own clearance. "
						"Choose another approver for {1}."
					).format(row.idx, frappe.bold(row.department))
				)
			if row.alternate_approver and row.alternate_approver == row.approver:
				frappe.throw(_("Row {0}: Alternate Approver must differ from Approver").format(row.idx))

	def block_manual_changes(self):
		"""Once the clearance has been sent, rows and system fields change only via the
		whitelisted actions below, never through a plain form save."""
		if self.flags.in_clearance_action or self.is_new():
			return
		before = self.get_doc_before_save()
		if not before or before.overall_status == "Draft":
			return

		def norm(value):
			return "" if value in (None, "") else str(value)

		for field in (
			"employee",
			"overall_status",
			"employee_acknowledgement",
			"employee_signature",
			"acknowledged_by_hr",
			"acknowledged_by",
			"signed_copy",
		):
			if norm(before.get(field)) != norm(self.get(field)):
				frappe.throw(
					_("{0} can only be changed through the clearance actions").format(
						frappe.bold(_(self.meta.get_label(field)))
					)
				)

		def snapshot(rows):
			return [
				(
					r.name,
					r.department,
					r.approver,
					r.alternate_approver,
					r.status,
					cint(r.has_custody),
					norm(r.custody_details),
					flt(r.amount_due),
					norm(r.remarks),
				)
				for r in rows
			]

		if snapshot(before.clearance_departments) != snapshot(self.clearance_departments):
			frappe.throw(
				_("Departments can only be edited while the clearance is in Draft. Use the Department Action buttons."),
				title=_("Not Allowed"),
			)

	# ---------------------------------------------------------------- status
	def set_overall_status(self):
		if self.overall_status not in ACTIVE_STATES:
			return
		rows = self.clearance_departments
		if any(r.status == "Pending" for r in rows):
			self.overall_status = "In Clearance"
		elif any(r.status == "Has Custody" for r in rows):
			self.overall_status = "On Hold"
		else:
			self.overall_status = "Pending Employee Acknowledgement"

	def set_total_amount_due(self):
		self.total_amount_due = sum(
			flt(r.amount_due) for r in self.clearance_departments if r.status == "Has Custody"
		)

	# ------------------------------------------------------------ population
	def populate_departments(self):
		settings = frappe.get_single(SETTINGS)
		rows = [d for d in settings.departments if d.is_active]
		if not rows:
			frappe.throw(
				_("Please add at least one active department in {0} first.").format(
					frappe.get_desk_link(SETTINGS, SETTINGS)
				)
			)
		for d in rows:
			self.append(
				"clearance_departments",
				{
					"department": d.department,
					"approver": d.approver,
					"alternate_approver": d.alternate_approver,
					"instructions": d.instructions,
					"status": "Pending",
				},
			)

	# ----------------------------------------------------------- assignments
	def notifications_enabled(self):
		value = frappe.db.get_single_value(SETTINGS, "notify_approvers")
		return 1 if value is None else int(value)

	def wanted_assignees(self):
		wanted = {}
		if self.docstatus != 0:
			return wanted
		if self.overall_status in ("In Clearance", "On Hold", "Pending Employee Acknowledgement"):
			for row in self.clearance_departments:
				if row.status == "Pending" and row.approver:
					wanted.setdefault(
						row.approver,
						_("Please review custody clearance for {0} - {1} department").format(
							self.employee_name, row.department
						),
					)
		if self.overall_status == "Pending Employee Acknowledgement":
			if self.user_id:
				wanted[self.user_id] = _("All departments cleared your custody. Please acknowledge the clearance.")
			elif self.owner:
				wanted[self.owner] = _(
					"{0} has no user. Collect the signed clearance copy and acknowledge on their behalf."
				).format(self.employee_name)
		if self.overall_status == "On Hold" and self.owner:
			wanted.setdefault(self.owner, _("A department reported outstanding custody for {0}").format(self.employee_name))
		return wanted

	def sync_assignments(self):
		try:
			wanted = self.wanted_assignees()
			current = set(
				frappe.get_all(
					"ToDo",
					filters={"reference_type": DOCTYPE, "reference_name": self.name, "status": "Open"},
					pluck="allocated_to",
				)
			)
			for user in current - set(wanted):
				assign_to.remove(DOCTYPE, self.name, user, ignore_permissions=True)
			for user in set(wanted) - current:
				assign_to.add(
					{
						"assign_to": [user],
						"doctype": DOCTYPE,
						"name": self.name,
						"description": wanted[user],
						"notify": self.notifications_enabled(),
					},
					ignore_permissions=True,
				)
		except Exception:
			# Notifications must never block the clearance itself
			frappe.log_error(title="Custody Clearance: assignment sync failed")


# ------------------------------------------------------------------ helpers
def _get_doc(name, for_update=True):
	# Row-level DB lock held until the request's transaction ends. Do not use
	# Document.lock(): it is a file lock that blocks our own doc.save() and can go stale.
	if for_update:
		frappe.db.get_value(DOCTYPE, name, "name", for_update=True)
	return frappe.get_doc(DOCTYPE, name)


def _notify(user, subject, doc):
	if not user:
		return
	try:
		frappe.get_doc(
			{
				"doctype": "Notification Log",
				"for_user": user,
				"type": "Alert",
				"subject": subject,
				"document_type": DOCTYPE,
				"document_name": doc.name,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="Custody Clearance: notification failed")


# ------------------------------------------------------------------ actions
@frappe.whitelist()
def send_for_clearance(name):
	"""HR sends the draft to every department at once (parallel approval)."""
	doc = _get_doc(name)
	doc.check_permission("write")

	if doc.docstatus != 0 or doc.overall_status != "Draft":
		frappe.throw(_("Only a Draft clearance can be sent."))
	if not doc.clearance_departments:
		frappe.throw(_("Add at least one department before sending."))
	doc.flags.in_clearance_action = True
	doc.overall_status = "In Clearance"
	doc.save()
	doc.add_comment("Info", _("Sent to {0} departments for parallel clearance").format(len(doc.clearance_departments)))
	if not doc.user_id:
		frappe.msgprint(
			_("{0} has no user account. HR will acknowledge on the employee's behalf with a signed copy.").format(
				frappe.bold(doc.employee_name)
			),
			alert=True,
		)
	return doc.overall_status


@frappe.whitelist()
def update_department_status(name, row_name, status, custody_details=None, amount_due=0, remarks=None):
	"""A department approver clears their department or reports outstanding custody."""
	if status not in ("Cleared", "Has Custody"):
		frappe.throw(_("Invalid status"))

	doc = _get_doc(name)
	if doc.docstatus != 0 or doc.overall_status not in ACTIVE_STATES:
		frappe.throw(_("This clearance is not open for department action."))

	row = next((r for r in doc.clearance_departments if r.name == row_name), None)
	if not row:
		frappe.throw(_("Department row not found"))

	user = frappe.session.user
	if user not in (row.approver, row.alternate_approver) and "System Manager" not in frappe.get_roles(user):
		frappe.throw(
			_("Only the approver of {0} can action this row.").format(frappe.bold(row.department)),
			frappe.PermissionError,
		)

	amount = flt(amount_due)
	if status == "Has Custody":
		if not (custody_details or "").strip():
			frappe.throw(_("Please describe the outstanding custody."))
		has_custody = 1
	else:
		if amount > 0:
			frappe.throw(_("A department with an amount due cannot be marked Cleared."))
		has_custody, custody_details, amount = 0, None, 0

	previous_status = doc.overall_status
	row.status = status
	row.has_custody = has_custody
	row.custody_details = custody_details
	row.amount_due = amount
	row.remarks = remarks
	row.approved_by = user
	row.approved_on = now_datetime()

	doc.flags.in_clearance_action = True
	doc.flags.ignore_permissions = True
	doc.save()

	doc.add_comment(
		"Info",
		_("{0}: {1} by {2}").format(
			row.department, _(status), get_fullname(user)
		),
	)
	if doc.overall_status == "Pending Employee Acknowledgement" and previous_status != doc.overall_status:
		_notify(doc.owner, _("All departments cleared {0}. Waiting for employee acknowledgement.").format(doc.employee_name), doc)

	return {"overall_status": doc.overall_status}


@frappe.whitelist()
def acknowledge(name, signature=None):
	"""The employee confirms the clearance. Only the linked user may do this."""
	doc = _get_doc(name)

	employee_user = frappe.db.get_value("Employee", doc.employee, "user_id")
	if not employee_user:
		frappe.throw(
			_("This employee has no user account. HR must acknowledge on the employee's behalf."),
			frappe.PermissionError,
		)
	if frappe.session.user != employee_user:
		frappe.throw(
			_("Only the employee on this clearance can acknowledge it."), frappe.PermissionError
		)
	if doc.docstatus != 0 or doc.overall_status != "Pending Employee Acknowledgement":
		frappe.throw(_("This clearance is not waiting for your acknowledgement."))

	doc.employee_signature = signature or None
	_complete(doc)
	doc.add_comment("Info", _("Employee acknowledged the clearance"))
	_notify(doc.owner, _("{0} acknowledged the custody clearance. Completed.").format(doc.employee_name), doc)
	return doc.overall_status


@frappe.whitelist()
def acknowledge_on_behalf(name, signed_copy):
	"""HR acknowledges for an employee who has no user account, backed by a signed paper copy."""
	if not _can_acknowledge_on_behalf():
		frappe.throw(
			_("Only users with the role {0} can acknowledge on an employee's behalf.").format(
				frappe.bold(_get_behalf_role())
			),
			frappe.PermissionError,
		)

	doc = _get_doc(name)
	if frappe.db.get_value("Employee", doc.employee, "user_id"):
		frappe.throw(_("This employee has a user account and must acknowledge the clearance personally."))
	if doc.docstatus != 0 or doc.overall_status != "Pending Employee Acknowledgement":
		frappe.throw(_("This clearance is not waiting for acknowledgement."))
	if not signed_copy:
		frappe.throw(_("Attach the signed clearance copy first."))

	file_name = frappe.db.get_value("File", {"file_url": signed_copy}, "name")
	if not file_name:
		frappe.throw(_("The signed copy was not found. Upload it again."))
	frappe.db.set_value(
		"File",
		file_name,
		{"attached_to_doctype": DOCTYPE, "attached_to_name": doc.name, "attached_to_field": "signed_copy"},
	)

	doc.acknowledged_by_hr = 1
	doc.acknowledged_by = frappe.session.user
	doc.signed_copy = signed_copy
	_complete(doc)

	doc.add_comment(
		"Info",
		_("{0} acknowledged on behalf of the employee, signed copy attached").format(
			get_fullname(frappe.session.user)
		),
	)
	_notify(doc.owner, _("{0} custody clearance completed (acknowledged by HR).").format(doc.employee_name), doc)
	return doc.overall_status


def _get_behalf_role():
	return frappe.db.get_single_value(SETTINGS, "on_behalf_role") or "HR Manager"


def _can_acknowledge_on_behalf():
	roles = set(frappe.get_roles())
	return _get_behalf_role() in roles or "System Manager" in roles


@frappe.whitelist()
def can_acknowledge_on_behalf():
	return _can_acknowledge_on_behalf()


def _complete(doc):
	doc.flags.in_clearance_action = True
	doc.flags.ignore_permissions = True
	doc.employee_acknowledgement = 1
	doc.acknowledgement_on = now_datetime()
	doc.overall_status = "Completed"
	doc.submit()


# ------------------------------------------------------------- permissions
def _related_condition(user):
	u = frappe.db.escape(user)
	cond = (
		"exists (select 1 from `tabCustody Clearance Department` d "
		"where d.parent = `tabCustody Clearance`.name "
		f"and (d.approver = {u} or d.alternate_approver = {u}))"
	)
	employee = frappe.db.get_value("Employee", {"user_id": user}, "name")
	if employee:
		cond += f" or `tabCustody Clearance`.employee = {frappe.db.escape(employee)}"
	return f"({cond})"


def get_permission_query_conditions(user=None):
	user = user or frappe.session.user
	if user == "Administrator" or HR_ROLES & set(frappe.get_roles(user)):
		return ""
	return _related_condition(user)


def has_permission(doc, ptype=None, user=None):
	user = user or frappe.session.user
	if user == "Administrator" or HR_ROLES & set(frappe.get_roles(user)):
		return None

	if user == doc.get("user_id"):
		return None
	if any(user in (r.approver, r.alternate_approver) for r in doc.get("clearance_departments") or []):
		return None
	return False
