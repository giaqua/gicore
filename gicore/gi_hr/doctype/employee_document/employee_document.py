# Copyright (c) 2026, GI Aqua Tech and contributors
# Controller for Employee Document (child table on Employee)

import frappe
from frappe.model.document import Document
from frappe.utils import getdate


class EmployeeDocument(Document):
    def validate(self):
        if self.issue_date and self.expiry_date and getdate(self.issue_date) > getdate(self.expiry_date):
            frappe.throw(
                f"Row {self.idx}: Issue Date cannot be after Expiry Date for {self.document_type or 'this document'}."
            )

        # Reset the reminder tracker if the expiry date was extended/renewed,
        # so the 90/60/30 cycle starts fresh for the new expiry date instead
        # of staying silent because an old threshold was already "used up".
        if self.has_value_changed("expiry_date"):
            self.last_notified_threshold = ""