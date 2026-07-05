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


# gicore/gi_support/api/report_issue.py

# import frappe

# @frappe.whitelist()
# def create_issue(subject, description, priority="Medium", file_url=None,
#                   route=None, reference_doctype=None, reference_name=None):
#     issue = frappe.get_doc({
#         "doctype": "Issue",
#         "subject": subject,
#         "description": description,
#         "priority": priority,
#         "raised_by": frappe.session.user,
#         "custom_page_route": route,               # add these as custom fields if you want context
#         "custom_reference_doctype": reference_doctype,
#         "custom_reference_name": reference_name,
#     })

#     print(f"========================================Creating issue with subject: {subject}, description: {description}, priority: {priority}, route: {route}, reference_doctype: {reference_doctype}, reference_name: {reference_name}, file_url: {file_url}")
#     issue.insert(ignore_permissions=True)

#     if file_url:
#         # re-link the already-uploaded file to this Issue
#         file_doc = frappe.get_all("File", filters={"file_url": file_url}, limit=1)
#         if file_doc:
#             f = frappe.get_doc("File", file_doc[0].name)
#             f.attached_to_doctype = "Issue"
#             f.attached_to_name = issue.name
#             f.save(ignore_permissions=True)

#     frappe.db.commit()
#     return issue.name


@frappe.whitelist()
def get_my_issues():
    """Return all issues raised by the current logged-in user."""
    issues = frappe.get_all(
        "Issue",
        filters={"raised_by": frappe.session.user},
        fields=[
            "name", "subject", "status", "priority",
            "creation", "modified", "opening_date", "opening_time"
        ],
        order_by="creation desc",
        limit_page_length=0,
        ignore_permissions=True
    )
    return issues