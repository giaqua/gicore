"""
task_tracker.py  —  Controller for the Task Tracker custom page.

Place this file at:
  <your_app>/page/task_tracker/task_tracker.py

The matching page record (DocType: Page) should have:
  - Page Name : task-tracker
  - Module    : <your module>
  - Script    : task_tracker.js
"""

import frappe
from frappe import _


# ── Page entry point ────────────────────────────────────────────────────────
def get_context(context):
    context.no_cache = 1


# ── Whitelisted API methods ─────────────────────────────────────────────────

@frappe.whitelist()
def get_tasks(
    search="",
    project="",
    task_type="",
    status="",
    page=1,
    page_size=50,
):
    """
    Return paginated task list with summary counts for the stat bar.
    """
    page      = int(page)
    page_size = int(page_size)
    filters   = {}

    if project:
        filters["project"] = project
    if task_type:
        filters["type"] = task_type
    if status:
        filters["status"] = status

    fields = [
        "name", "subject", "status", "type",
        "project", "priority", "exp_end_date",
        "progress", "description",
        "assigned_to", "_assign",
        "parent_task", "modified",
    ]

    # Subject / name search
    if search:
        tasks = frappe.get_list(
            "Task",
            filters=filters,
            or_filters=[
                ["subject", "like", f"%{search}%"],
                ["name",    "like", f"%{search}%"],
            ],
            fields=fields,
            order_by="modified desc",
            limit_page_length=page_size,
            limit_start=(page - 1) * page_size,
        )
        total = frappe.db.count(
            "Task",
            filters={**filters, "subject": ("like", f"%{search}%")},
        )
    else:
        tasks = frappe.get_list(
            "Task",
            filters=filters,
            fields=fields,
            order_by="modified desc",
            limit_page_length=page_size,
            limit_start=(page - 1) * page_size,
        )
        total = frappe.db.count("Task", filters=filters)

    # Resolve parent task subject
    parent_names = list({t.parent_task for t in tasks if t.parent_task})
    parent_map   = {}
    if parent_names:
        for row in frappe.get_list(
            "Task",
            filters=[["name", "in", parent_names]],
            fields=["name", "subject"],
        ):
            parent_map[row.name] = row.subject

    for t in tasks:
        t["parent_task_subject"] = parent_map.get(t.parent_task, t.parent_task or "")
        # Parse _assign JSON → first assignee display
        try:
            import json
            assigns = json.loads(t._assign or "[]")
            t["assignee"] = assigns[0] if assigns else ""
        except Exception:
            t["assignee"] = ""

    # Summary counts (unfiltered by pagination)
    counts = {
        "total":    frappe.db.count("Task", {"project": project} if project else {}),
        "open":     frappe.db.count("Task", {**({"project": project} if project else {}), "status": "Open"}),
        "working":  frappe.db.count("Task", {**({"project": project} if project else {}), "status": "Working"}),
        "overdue":  frappe.db.count("Task", {**({"project": project} if project else {}), "status": "Overdue"}),
        "completed":frappe.db.count("Task", {**({"project": project} if project else {}), "status": "Completed"}),
    }

    return {
        "tasks":    tasks,
        "total":    total,
        "page":     page,
        "page_size":page_size,
        "counts":   counts,
    }


@frappe.whitelist()
def get_filter_options():
    """Return distinct projects and task types for filter dropdowns."""
    projects = frappe.get_list(
        "Project",
        fields=["name", "project_name"],
        filters={"status": ("!=", "Cancelled")},
        order_by="project_name asc",
        limit_page_length=500,
    )
    task_types = frappe.db.sql(
        "SELECT DISTINCT `type` FROM `tabTask` WHERE `type` IS NOT NULL AND `type` != '' ORDER BY `type`",
        as_dict=True,
    )
    return {
        "projects":   projects,
        "task_types": [r.type for r in task_types],
    }


@frappe.whitelist()
def get_task_detail(task_name):
    """Return full task record for the quick-review panel."""
    doc = frappe.get_doc("Task", task_name)
    frappe.has_permission("Task", "read", doc, throw=True)

    import json
    assigns = []
    try:
        assigns = json.loads(doc._assign or "[]")
    except Exception:
        pass

    comments = frappe.get_list(
        "Comment",
        filters={"reference_doctype": "Task", "reference_name": task_name, "comment_type": "Comment"},
        fields=["content", "comment_by", "creation"],
        order_by="creation asc",
        limit_page_length=20,
    )

    return {
        "name":            doc.name,
        "subject":         doc.subject,
        "status":          doc.status,
        "type":            doc.type,
        "project":         doc.project,
        "priority":        doc.priority,
        "exp_start_date":  str(doc.exp_start_date or ""),
        "exp_end_date":    str(doc.exp_end_date or ""),
        "progress":        doc.progress or 0,
        "description":     doc.description or "",
        "parent_task":     doc.parent_task or "",
        "assignees":       assigns,
        "comments":        [
            {
                "content":    c.content,
                "comment_by": c.comment_by,
                "creation":   str(c.creation),
            }
            for c in comments
        ],
    }


@frappe.whitelist()
def update_task_status(task_name, status):
    """Quick inline status update."""
    doc = frappe.get_doc("Task", task_name)
    frappe.has_permission("Task", "write", doc, throw=True)
    doc.status = status
    doc.save(ignore_permissions=False)
    return {"ok": True, "status": doc.status}


@frappe.whitelist()
def create_task(subject, project="", task_type="", priority="Medium", description=""):
    """Create a new Task and return its name."""
    doc = frappe.new_doc("Task")
    doc.subject     = subject
    doc.project     = project or None
    doc.type        = task_type or None
    doc.priority    = priority
    doc.description = description
    doc.status      = "Open"
    doc.insert(ignore_permissions=False)
    frappe.db.commit()
    return {"name": doc.name, "subject": doc.subject}
