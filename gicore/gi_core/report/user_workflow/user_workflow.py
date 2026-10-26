import frappe
from frappe import _


def execute(filters=None):
    filters = filters or {}
    return get_columns(), get_data(filters)


def get_columns():
    return [
        {"label": _("User"), "fieldname": "user", "fieldtype": "Link", "options": "User", "width": 220},
        {"label": _("Full Name"), "fieldname": "full_name", "fieldtype": "Data", "width": 180},
        {"label": _("DocType"), "fieldname": "document_type", "fieldtype": "Link", "options": "DocType", "width": 180},
        {"label": _("Workflow"), "fieldname": "workflow", "fieldtype": "Link", "options": "Workflow", "width": 180},
        {"label": _("Role"), "fieldname": "role", "fieldtype": "Link", "options": "Role", "width": 150},
        {"label": _("Role Used In"), "fieldname": "source", "fieldtype": "Data", "width": 160},
    ]


def get_data(filters):
    conditions = ""
    if filters.get("user"):
        conditions += " AND hr.parent = %(user)s"
    if filters.get("document_type"):
        conditions += " AND w.document_type = %(document_type)s"
    if filters.get("workflow"):
        conditions += " AND w.name = %(workflow)s"
    if filters.get("role"):
        conditions += " AND r.role = %(role)s"
    if not filters.get("include_inactive"):
        conditions += " AND w.is_active = 1"

    return frappe.db.sql(
        f"""
        SELECT
            hr.parent AS user,
            u.full_name AS full_name,
            w.document_type AS document_type,
            w.name AS workflow,
            r.role AS role,
            GROUP_CONCAT(DISTINCT r.source ORDER BY r.source SEPARATOR ', ') AS source
        FROM (
            SELECT parent AS workflow, allowed AS role, 'Transition' AS source
            FROM `tabWorkflow Transition`
            UNION ALL
            SELECT parent AS workflow, allow_edit AS role, 'State (Edit)' AS source
            FROM `tabWorkflow Document State`
        ) r
        INNER JOIN `tabWorkflow` w ON w.name = r.workflow
        INNER JOIN `tabHas Role` hr ON hr.role = r.role AND hr.parenttype = 'User'
        INNER JOIN `tabUser` u ON u.name = hr.parent AND u.enabled = 1
        WHERE 1 = 1 {conditions}
        GROUP BY hr.parent, u.full_name, w.document_type, w.name, r.role
        ORDER BY hr.parent, w.document_type
        """,
        filters,
        as_dict=True,
    )