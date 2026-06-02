"""
PO Payment Status Report
Shows Purchase Orders with Invoice Amount, Paid Amount, and Pending Amount.

Filters: Company, From Date, To Date, Supplier, Supplier Group, Purchase Order
"""

import frappe
from frappe import _
from frappe.utils import flt


def execute(filters=None):
    filters = filters or {}
    columns = get_columns()
    data = get_data(filters)
    return columns, data


def get_columns():
    return [
        {
            "label": _("Purchase Order"),
            "fieldname": "purchase_order",
            "fieldtype": "Link",
            "options": "Purchase Order",
            "width": 160,
        },
        {
            "label": _("Date"),
            "fieldname": "transaction_date",
            "fieldtype": "Date",
            "width": 100,
        },
        {
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 160,
        },
        {
            "label": _("Supplier Name"),
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 180,
        },
        # {
        #     "label": _("Supplier Group"),
        #     "fieldname": "supplier_group",
        #     "fieldtype": "Link",
        #     "options": "Supplier Group",
        #     "width": 130,
        # },
        # {
        #     "label": _("Company"),
        #     "fieldname": "company",
        #     "fieldtype": "Link",
        #     "options": "Company",
        #     "width": 130,
        # },
        {
            "label": _("Currency"),
            "fieldname": "currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 80,
        },
        {
            "label": _("PO Amount"),
            "fieldname": "po_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": _("Invoiced Amount"),
            "fieldname": "invoiced_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": _("Paid Amount"),
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": _("Outstanding Amount"),
            "fieldname": "outstanding_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": _("Status"),
            "fieldname": "status",
            "fieldtype": "Data",
            "width": 110,
        },
    ]


def get_data(filters):
    conditions, values = get_conditions(filters)

    # ── 1. Fetch Purchase Orders ──────────────────────────────────────────────
    po_list = frappe.db.sql(
        """
        SELECT
            po.name            AS purchase_order,
            po.transaction_date,
            po.supplier,
            po.supplier_name,
            s.supplier_group,
            po.company,
            po.currency,
            po.grand_total     AS po_amount,
            po.status
        FROM `tabPurchase Order` po, `tabSupplier` s
        WHERE po.docstatus = 1 AND po.supplier = s.name
          {conditions}
        ORDER BY po.transaction_date, po.name
        """.format(conditions=conditions),
        values,
        as_dict=True,
    )

    if not po_list:
        return []

    po_names = [d["purchase_order"] for d in po_list]

    # ── 2. Invoiced amount per PO (via Purchase Invoice Items) ────────────────
    invoiced_map = _get_invoiced_map(po_names)

    # ── 3. Paid amount per PO — two sources:
    #       a) Payments linked directly to PO (Payment Entry Reference)
    #       b) Payments linked to Purchase Invoices that came from this PO
    paid_map = _get_paid_map(po_names)

    # ── 4. Assemble rows ──────────────────────────────────────────────────────
    data = []
    for row in po_list:
        po = row["purchase_order"]
        po_amount       = flt(row["po_amount"])
        invoiced_amount = flt(invoiced_map.get(po, 0))
        paid_amount     = flt(paid_map.get(po, 0))

        # Outstanding = PO Amount - Paid Amount
        outstanding_amount = max(po_amount - paid_amount, 0)

        # Status: Fully Paid only when paid amount covers the full PO
        display_status = "Fully Paid" if paid_amount >= po_amount else "Not Paid"

        data.append(
            {
                "purchase_order":    po,
                "transaction_date":  row["transaction_date"],
                "supplier":          row["supplier"],
                "supplier_name":     row["supplier_name"],
                "supplier_group":    row["supplier_group"],
                "company":           row["company"],
                "currency":          row["currency"],
                "po_amount":         po_amount,
                "invoiced_amount":   invoiced_amount,
                "paid_amount":       paid_amount,
                "outstanding_amount": outstanding_amount,
                "status":            display_status,
            }
        )

    # Filter by status if specified (computed field, not in SQL)
    if filters.get("status"):
        data = [d for d in data if d["status"] == filters["status"]]

    return data


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_conditions(filters):
    """Build WHERE clause fragments for the PO query."""
    conditions = []
    values = {}

    if filters.get("company"):
        conditions.append("po.company = %(company)s")
        values["company"] = filters["company"]

    if filters.get("from_date"):
        conditions.append("po.transaction_date >= %(from_date)s")
        values["from_date"] = filters["from_date"]

    if filters.get("to_date"):
        conditions.append("po.transaction_date <= %(to_date)s")
        values["to_date"] = filters["to_date"]

    if filters.get("supplier"):
        conditions.append("po.supplier = %(supplier)s")
        values["supplier"] = filters["supplier"]

    if filters.get("supplier_group"):
        conditions.append("po.supplier_group = %(supplier_group)s")
        values["supplier_group"] = filters["supplier_group"]

    if filters.get("purchase_order"):
        conditions.append("po.name = %(purchase_order)s")
        values["purchase_order"] = filters["purchase_order"]

    clause = ("AND " + " AND ".join(conditions)) if conditions else ""
    return clause, values


def _get_invoiced_map(po_names):
    """
    Sum of submitted Purchase Invoice line amounts mapped back to the source PO.
    Uses `purchase_order` field on Purchase Invoice Item.
    """
    if not po_names:
        return {}

    rows = frappe.db.sql(
        """
        SELECT
            pii.purchase_order,
            SUM(pii.total_amount) AS total_invoiced
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi
            ON pi.name = pii.parent
        WHERE pi.docstatus = 1
          AND pii.purchase_order IN %(po_names)s
        GROUP BY pii.purchase_order
        """,
        {"po_names": po_names},
        as_dict=True,
    )
    return {r["purchase_order"]: flt(r["total_invoiced"]) for r in rows}


def _get_paid_map(po_names):
    """
    Aggregate paid amounts per PO from two channels:

    Channel A – Payment Entry References pointing directly at the PO
    Channel B – Payment Entry References pointing at Purchase Invoices
                that were created from the PO
    """
    if not po_names:
        return {}

    paid_map = {}

    # ── Channel A: direct PO references ──────────────────────────────────────
    rows_a = frappe.db.sql(
        """
        SELECT
            per.reference_name  AS purchase_order,
            SUM(per.allocated_amount) AS paid
        FROM `tabPayment Entry Reference` per
        INNER JOIN `tabPayment Entry` pe
            ON pe.name = per.parent
        WHERE pe.docstatus = 1
          AND pe.payment_type = 'Pay'
          AND per.reference_doctype = 'Purchase Order'
          AND per.reference_name IN %(po_names)s
        GROUP BY per.reference_name
        """,
        {"po_names": po_names},
        as_dict=True,
    )
    for r in rows_a:
        paid_map[r["purchase_order"]] = flt(paid_map.get(r["purchase_order"], 0)) + flt(r["paid"])

    # ── Channel B: payments made against invoices that link to this PO ────────
    # First, find all invoices linked to our POs
    invoice_to_po = {}
    inv_rows = frappe.db.sql(
        """
        SELECT DISTINCT pii.parent AS invoice, pii.purchase_order
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.docstatus = 1
          AND pii.purchase_order IN %(po_names)s
        """,
        {"po_names": po_names},
        as_dict=True,
    )
    for r in inv_rows:
        invoice_to_po[r["invoice"]] = r["purchase_order"]

    if invoice_to_po:
        invoice_names = list(invoice_to_po.keys())
        rows_b = frappe.db.sql(
            """
            SELECT
                per.reference_name  AS invoice,
                SUM(per.allocated_amount) AS paid
            FROM `tabPayment Entry Reference` per
            INNER JOIN `tabPayment Entry` pe
                ON pe.name = per.parent
            WHERE pe.docstatus = 1
              AND pe.payment_type = 'Pay'
              AND per.reference_doctype = 'Purchase Invoice'
              AND per.reference_name IN %(invoice_names)s
            GROUP BY per.reference_name
            """,
            {"invoice_names": invoice_names},
            as_dict=True,
        )
        for r in rows_b:
            po = invoice_to_po.get(r["invoice"])
            if po:
                paid_map[po] = flt(paid_map.get(po, 0)) + flt(r["paid"])

    # ── Channel C: Journal Entry payments against Purchase Invoices linked to PO
    if invoice_to_po:
        invoice_names = list(invoice_to_po.keys())
        rows_c = frappe.db.sql(
            """
            SELECT
                jea.reference_name  AS invoice,
                SUM(ABS(jea.credit_in_account_currency)) AS paid
            FROM `tabJournal Entry Account` jea
            INNER JOIN `tabJournal Entry` je ON je.name = jea.parent
            WHERE je.docstatus = 1
              AND jea.reference_type = 'Purchase Invoice'
              AND jea.reference_name IN %(invoice_names)s
            GROUP BY jea.reference_name
            """,
            {"invoice_names": invoice_names},
            as_dict=True,
        )
        for r in rows_c:
            po = invoice_to_po.get(r["invoice"])
            if po:
                paid_map[po] = flt(paid_map.get(po, 0)) + flt(r["paid"])

    return paid_map
