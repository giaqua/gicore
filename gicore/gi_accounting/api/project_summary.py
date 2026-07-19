import frappe
from frappe import _

@frappe.whitelist()
def get_project_transaction_summary(project):
    if not project:
        frappe.throw(_("Project is required"))
    frappe.has_permission("Project", doc=project, throw=True)

    summary = {}

    # ---- GL Entry: true financial net position by voucher type ----
    summary["gl_entry"] = frappe.db.sql("""
        SELECT voucher_type,
               COUNT(DISTINCT voucher_no) AS voucher_count,
               SUM(debit) AS total_debit,
               SUM(credit) AS total_credit
        FROM `tabGL Entry`
        WHERE project = %s AND is_cancelled = 0
        GROUP BY voucher_type
        ORDER BY voucher_type
    """, project, as_dict=1)

    summary["gl_totals"] = frappe.db.sql("""
        SELECT SUM(debit) AS total_debit, SUM(credit) AS total_credit
        FROM `tabGL Entry` WHERE project = %s AND is_cancelled = 0
    """, project, as_dict=1)[0]

    # ---- Sales side ----
    summary["sales_order"] = frappe.db.sql("""
        SELECT COUNT(*) AS count, SUM(grand_total) AS total
        FROM `tabSales Order` WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    summary["delivery_note"] = frappe.db.sql("""
        SELECT COUNT(*) AS count, SUM(grand_total) AS total
        FROM `tabDelivery Note` WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    summary["sales_invoice"] = frappe.db.sql("""
        SELECT COUNT(*) AS count, SUM(grand_total) AS total,
               SUM(outstanding_amount) AS outstanding, SUM(paid_amount) AS paid
        FROM `tabSales Invoice` WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    # ---- Purchase side ----
    summary["purchase_order"] = frappe.db.sql("""
        SELECT COUNT(*) AS count, SUM(grand_total) AS total
        FROM `tabPurchase Order` WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    summary["purchase_receipt"] = frappe.db.sql("""
        SELECT COUNT(*) AS count, SUM(grand_total) AS total
        FROM `tabPurchase Receipt` WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    summary["purchase_invoice"] = frappe.db.sql("""
        SELECT COUNT(*) AS count, SUM(grand_total) AS total,
               SUM(outstanding_amount) AS outstanding, SUM(paid_amount) AS paid
        FROM `tabPurchase Invoice` WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    # ---- Journal Entry: project lives on the child table, not the parent ----
    summary["journal_entry"] = frappe.db.sql("""
        SELECT COUNT(DISTINCT je.name) AS count,
               SUM(jea.debit) AS total_debit, SUM(jea.credit) AS total_credit
        FROM `tabJournal Entry Account` jea
        INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
        WHERE jea.project = %s AND je.docstatus = 1
    """, project, as_dict=1)[0]

    # ---- Payment Entry: NO project field exists on this doctype by default.
    # Derived via Payment Entry Reference -> the SI/PI that belongs to this project.
    summary["payment_entry"] = frappe.db.sql("""
        SELECT pe.payment_type,
               COUNT(DISTINCT pe.name) AS count,
               SUM(per.allocated_amount) AS total_allocated
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
        WHERE pe.docstatus = 1
          AND (
            (per.reference_doctype = 'Sales Invoice' AND per.reference_name IN
                (SELECT name FROM `tabSales Invoice` WHERE project = %(project)s))
            OR
            (per.reference_doctype = 'Purchase Invoice' AND per.reference_name IN
                (SELECT name FROM `tabPurchase Invoice` WHERE project = %(project)s))
          )
        GROUP BY pe.payment_type
    """, {"project": project}, as_dict=1)

    # ---- Other transactions people forget ----
    summary["stock_entry"] = frappe.db.sql("""
        SELECT COUNT(*) AS count FROM `tabStock Entry`
        WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    summary["material_request"] = frappe.db.sql("""
        SELECT COUNT(*) AS count FROM `tabMaterial Request`
        WHERE custom_project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    summary["expense_claim"] = frappe.db.sql("""
        SELECT COUNT(*) AS count, SUM(total_sanctioned_amount) AS total
        FROM `tabExpense Claim` WHERE project = %s AND docstatus = 1
    """, project, as_dict=1)[0]

    # Timesheet: project also lives on the child table (Timesheet Detail)
    summary["timesheet"] = frappe.db.sql("""
        SELECT COUNT(DISTINCT ts.name) AS count, SUM(tsd.billing_amount) AS billable
        FROM `tabTimesheet Detail` tsd
        INNER JOIN `tabTimesheet` ts ON ts.name = tsd.parent
        WHERE tsd.project = %s AND ts.docstatus = 1
    """, project, as_dict=1)[0]

    return summary