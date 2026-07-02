# gicore/gicore/api/report_issue.py

import frappe

@frappe.whitelist()
def create_issue(subject, description, priority="Medium", screenshot=None,
                  route=None, reference_doctype=None, reference_name=None):
    issue = frappe.get_doc({
        "doctype": "Issue",
        "subject": subject,
        "description": description,
        "priority": priority,
        "raised_by": frappe.session.user,
        "custom_page_route": route,               # add these as custom fields if you want context
        "custom_reference_doctype": reference_doctype,
        "custom_reference_name": reference_name,
    })
    issue.insert(ignore_permissions=True)

    if screenshot:
        # attach the screenshot file to the Issue
        frappe.get_doc({
            "doctype": "File",
            "file_url": screenshot,
            "attached_to_doctype": "Issue",
            "attached_to_name": issue.name
        }).insert(ignore_permissions=True)

    frappe.db.commit()
    return issue.name