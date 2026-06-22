# Copyright (c) 2026, GI Aqua Tech and contributors
# Employee Document Expiry — Script Report

import frappe
from frappe.utils import date_diff, getdate, nowdate


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {"label": "Employee", "fieldname": "employee", "fieldtype": "Link", "options": "Employee", "width": 120},
        {"label": "Employee Name", "fieldname": "employee_name", "fieldtype": "Data", "width": 160},
        {"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 160},
        {"label": "Document Type", "fieldname": "document_type", "fieldtype": "Data", "width": 110},
        {"label": "Document Number", "fieldname": "document_number", "fieldtype": "Data", "width": 130},
        {"label": "Expiry Date", "fieldname": "expiry_date", "fieldtype": "Date", "width": 100},
        {"label": "Days Remaining", "fieldname": "days_remaining", "fieldtype": "Int", "width": 110},
        {"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 110},
    ]


def get_data(filters):
    conditions = ["e.status = 'Active'", "ed.expiry_date is not null"]
    values = {}

    if filters.get("company"):
        conditions.append("e.company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("document_type"):
        conditions.append("ed.document_type = %(document_type)s")
        values["document_type"] = filters["document_type"]

    if filters.get("employee"):
        conditions.append("e.name = %(employee)s")
        values["employee"] = filters["employee"]

    rows = frappe.db.sql(f"""
        select
            e.name as employee, e.employee_name, e.company,
            ed.document_type, ed.document_number, ed.expiry_date
        from `tabEmployee Document` ed
        inner join `tabEmployee` e on e.name = ed.parent
        where {" and ".join(conditions)}
        order by ed.expiry_date asc
    """, values, as_dict=True)

    today = getdate(nowdate())
    status_filter = filters.get("status")  # All / Expired / Expiring / Valid
    result = []

    for row in rows:
        days_remaining = date_diff(getdate(row.expiry_date), today)
        row["days_remaining"] = days_remaining
        row["status"] = classify_status(days_remaining)

        if status_filter and status_filter != "All" and row["status"] != status_filter:
            continue

        result.append(row)

    return result


def classify_status(days_remaining):
    if days_remaining < 0:
        return "Expired"
    if days_remaining <= 30:
        return "Critical (<=30d)"
    if days_remaining <= 60:
        return "Warning (<=60d)"
    if days_remaining <= 90:
        return "Upcoming (<=90d)"
    return "Valid"