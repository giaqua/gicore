import frappe
from frappe.utils import nowdate


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": "User",
            "fieldname": "user",
            "fieldtype": "Link",
            "options": "User",
            "width": 220,
        },
        {
            "label": "DocType",
            "fieldname": "doctype",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": "Documents Created",
            "fieldname": "created",
            "fieldtype": "Int",
            "width": 150,
        },
        {
            "label": "Documents Updated",
            "fieldname": "updated",
            "fieldtype": "Int",
            "width": 160,
        },
        {
            "label": "Submitted (Not Creator)",
            "fieldname": "submitted_not_creator",
            "fieldtype": "Int",
            "width": 200,
        },
        {
            "label": "Documents Viewed",
            "fieldname": "viewed",
            "fieldtype": "Int",
            "width": 150,
        },
        {
            "label": "Total Activities",
            "fieldname": "total",
            "fieldtype": "Int",
            "width": 140,
        },
    ]


def get_data(filters):
    user_filter    = filters.get("user")
    doctype_filter = filters.get("doctype")
    from_date      = filters.get("from_date") or "2000-01-01"
    to_date        = filters.get("to_date")   or nowdate()

    params = {
        "from_date": from_date,
        "to_date":   to_date,
        "user":      user_filter,
        "doctype":   doctype_filter,
    }

    # ── shared condition snippets ──────────────────────────────────────
    ver_user_cond    = "AND v.owner = %(user)s"         if user_filter    else ""
    ver_doctype_cond = "AND v.ref_doctype = %(doctype)s" if doctype_filter else ""

    al_user_cond     = "AND al.user = %(user)s"                    if user_filter    else ""
    al_doctype_cond  = "AND al.reference_doctype = %(doctype)s"    if doctype_filter else ""

    # ── 1. Created ─────────────────────────────────────────────────────
    # First tabVersion row per document = the creation event
    created_rows = frappe.db.sql("""
        SELECT
            v.owner       AS user,
            v.ref_doctype AS doctype,
            COUNT(*)      AS created
        FROM `tabVersion` v
        INNER JOIN (
            SELECT ref_doctype, docname, MIN(name) AS first_ver
            FROM `tabVersion`
            GROUP BY ref_doctype, docname
        ) fv
            ON  fv.ref_doctype = v.ref_doctype
            AND fv.docname     = v.docname
            AND fv.first_ver   = v.name
        WHERE
            DATE(v.creation) BETWEEN %(from_date)s AND %(to_date)s
            {user_cond}
            {doctype_cond}
        GROUP BY v.owner, v.ref_doctype
    """.format(user_cond=ver_user_cond, doctype_cond=ver_doctype_cond),
        params, as_dict=True,
    )

    # ── 2. Updated ─────────────────────────────────────────────────────
    # Any tabVersion row that is NOT the first row for that document
    updated_rows = frappe.db.sql("""
        SELECT
            v.owner       AS user,
            v.ref_doctype AS doctype,
            COUNT(*)      AS updated
        FROM `tabVersion` v
        WHERE
            v.name NOT IN (
                SELECT MIN(name)
                FROM `tabVersion`
                GROUP BY ref_doctype, docname
            )
            AND DATE(v.creation) BETWEEN %(from_date)s AND %(to_date)s
            {user_cond}
            {doctype_cond}
        GROUP BY v.owner, v.ref_doctype
    """.format(user_cond=ver_user_cond, doctype_cond=ver_doctype_cond),
        params, as_dict=True,
    )

    # ── 3. Submitted where user is NOT the original creator ────────────
    # reference_owner in tabActivity Log holds the document owner (creator)
    # al.user is the person who performed the action
    submitted_rows = frappe.db.sql("""
        SELECT
            al.user               AS user,
            al.reference_doctype  AS doctype,
            COUNT(*)              AS submitted_not_creator
        FROM `tabActivity Log` al
        WHERE
            al.operation          = 'submitted'
            AND al.user          != al.reference_owner
            AND al.reference_owner IS NOT NULL
            AND al.reference_owner != ''
            AND DATE(al.creation) BETWEEN %(from_date)s AND %(to_date)s
            {user_cond}
            {doctype_cond}
        GROUP BY al.user, al.reference_doctype
    """.format(user_cond=al_user_cond, doctype_cond=al_doctype_cond),
        params, as_dict=True,
    )

    # ── 4. Viewed (from tabView Log) ───────────────────────────────────
    view_user_cond    = "AND vl.viewed_by = %(user)s"              if user_filter    else ""
    view_doctype_cond = "AND vl.reference_doctype = %(doctype)s"   if doctype_filter else ""

    viewed_rows = frappe.db.sql("""
        SELECT
            vl.viewed_by          AS user,
            vl.reference_doctype  AS doctype,
            COUNT(*)              AS viewed
        FROM `tabView Log` vl
        WHERE
            DATE(vl.creation) BETWEEN %(from_date)s AND %(to_date)s
            {user_cond}
            {doctype_cond}
        GROUP BY vl.viewed_by, vl.reference_doctype
    """.format(user_cond=view_user_cond, doctype_cond=view_doctype_cond),
        params, as_dict=True,
    )

    # ── Merge into unified result dict ─────────────────────────────────
    result = {}

    def upsert(rows, key):
        for row in rows:
            # skip rows with no user or doctype
            if not row.get("user") or not row.get("doctype"):
                continue
            k = (row["user"], row["doctype"])
            if k not in result:
                result[k] = {
                    "user":                  row["user"],
                    "doctype":               row["doctype"],
                    "created":               0,
                    "updated":               0,
                    "submitted_not_creator": 0,
                    "viewed":                0,
                }
            result[k][key] += row[key] or 0

    upsert(created_rows,   "created")
    upsert(updated_rows,   "updated")
    upsert(submitted_rows, "submitted_not_creator")
    upsert(viewed_rows,    "viewed")

    # ── Compute total and sort by total desc ───────────────────────────
    final = []
    for row in result.values():
        row["total"] = (
            row["created"] +
            row["updated"] +
            row["submitted_not_creator"] +
            row["viewed"]
        )
        final.append(row)

    final.sort(key=lambda x: (-x["total"], x["user"], x["doctype"]))
    return final