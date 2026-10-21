import frappe
from frappe import _
from frappe.model.document import Document


class CustodyClearanceSettings(Document):
	def validate(self):
		seen = set()
		for row in self.departments:
			if not row.is_active:
				continue
			if row.department in seen:
				frappe.throw(
					_("Row {0}: Department {1} is listed more than once").format(
						row.idx, frappe.bold(row.department)
					)
				)
			seen.add(row.department)
			if row.alternate_approver and row.alternate_approver == row.approver:
				frappe.throw(_("Row {0}: Alternate Approver must differ from Approver").format(row.idx))

		if not seen:
			frappe.msgprint(
				_("No active departments are configured. New clearances cannot be created until you add one."),
				indicator="orange",
			)
