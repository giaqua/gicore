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
    columns = get_columns(filters)
    data = get_data(filters)
    return columns, data


def get_columns(filters=None):
    columns = [
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
            "width": 100,
        },
        {
            "label": _("Supplier Name"),
            "fieldname": "supplier_name",
            "fieldtype": "Data",
            "width": 180,
        },
        {
            "label": _("PO Currency"),
            "fieldname": "po_currency",
            "fieldtype": "Link",
            "options": "Currency",
            "width": 100,
        },
        {
            "label": _("PO Amount (PO Currency)"),
            "fieldname": "po_amount",
            "fieldtype": "Currency",
            "options": "po_currency",
            "width": 130,
        }
    ]

    if filters.get("show_vat"):
        columns.extend([{
            "label": _("Invoiced Amount (SAR)"),
            "fieldname": "invoiced_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 140,
        },
        {
            "label": _("VAT Amount (SAR)"),
            "fieldname": "vat_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        }])

    columns.extend([ {
            "label": _("Invoiced Amount"),
            "fieldname": "total_invoice_with_vat",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": _("PO Amount Yet to Be Invoiced (SAR)"),
            "fieldname": "yet_to_be_invoiced",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": _("Paid Amount (SAR)"),
            "fieldname": "paid_amount",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 130,
        },
        {
            "label": _("Paid vs Invoiced (Difference)"),
            "fieldname": "paid_vs_invoiced",
            "fieldtype": "Currency",
            "options": "currency",
            "width": 150,
        },
        {
            "label": _("Outstanding Amount (SAR)"),
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
        }])
    
    return columns


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
            po.currency        AS po_currency,
            po.grand_total     AS po_amount,
            po.status
        FROM `tabPurchase Order` po
        INNER JOIN `tabSupplier` s ON po.supplier = s.name
        WHERE po.docstatus = 1
          {conditions}
        ORDER BY po.transaction_date, po.name
        """.format(conditions=conditions),
        values,
        as_dict=True,
    )

    if not po_list:
        return []

    po_names = [d["purchase_order"] for d in po_list]

    # ── 2. Get company currency (assuming SAR) ───────────────────────────────
    company_currency = frappe.db.get_value("Company", filters.get("company"), "default_currency") or "SAR"

    # ── 3. Invoiced amount per PO with VAT calculation ───────────────────────
    invoice_data = _get_invoice_data(po_names, company_currency)

    # ── 4. Paid amount per PO via GL Entry ───────────────────────────────────
    paid_map = _get_paid_map_via_gl(po_names)

    # ── 5. Assemble rows ──────────────────────────────────────────────────────
    data = []
    for row in po_list:
        po = row["purchase_order"]
        po_amount = flt(row["po_amount"])
        
        # Get invoice data
        invoice_info = invoice_data.get(po, {
            'invoiced_amount': 0,
            'vat_amount': 0,
            'total_with_vat': 0
        })
        
        invoiced_amount = flt(invoice_info['invoiced_amount'])
        vat_amount = flt(invoice_info['vat_amount'])
        total_invoice_with_vat = flt(invoice_info['total_with_vat'])
        paid_amount = flt(paid_map.get(po, 0))

        # Convert PO amount to SAR if needed (for comparison)
        # Assuming exchange rate if PO currency differs from SAR
        po_amount_in_sar = _convert_to_sar(po_amount, row["po_currency"], company_currency, row["transaction_date"])
        
        # Calculations
        yet_to_be_invoiced = max(po_amount_in_sar - total_invoice_with_vat, 0)
        paid_vs_invoiced = paid_amount - total_invoice_with_vat
        outstanding_amount = max(po_amount_in_sar - paid_amount, 0)

        # Status determination
        if paid_amount >= po_amount_in_sar:
            display_status = "Fully Paid"
        elif paid_amount > 0:
            display_status = "Partially Paid"
        else:
            display_status = "Not Paid"

        data.append({
            "purchase_order": po,
            "transaction_date": row["transaction_date"],
            "supplier": row["supplier"],
            "supplier_name": row["supplier_name"],
            "supplier_group": row["supplier_group"],
            "company": row["company"],
            "po_currency": row["po_currency"],
            "po_amount": po_amount,
            "invoiced_amount": invoiced_amount,
            "vat_amount": vat_amount,
            "total_invoice_with_vat": total_invoice_with_vat,
            "yet_to_be_invoiced": yet_to_be_invoiced,
            "paid_amount": paid_amount,
            "outstanding_amount": outstanding_amount,
            "status": display_status,
            "paid_vs_invoiced": paid_vs_invoiced,
            "currency": company_currency,  # Default currency for SAR amounts
        })

    # Filter by status if specified
    if filters.get("status"):
        data = [d for d in data if d["status"] == filters["status"]]

    return data


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

    clause = " AND " + " AND ".join(conditions) if conditions else ""
    return clause, values


def _get_invoice_data(po_names, company_currency):
    """
    Get invoice amounts including VAT from Purchase Invoices.
    Handles invoices with and without VAT properly.
    """
    if not po_names:
        return {}

    invoice_data = {}
    
    # Get Purchase Invoices linked to POs
    invoices = frappe.db.sql("""
        SELECT DISTINCT
            pi.name as invoice,
            pii.purchase_order,
            pi.base_net_total as net_total,
            pi.base_total_taxes_and_charges as tax_amount,
            pi.base_grand_total as grand_total
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.docstatus = 1
          AND pii.purchase_order IN %(po_names)s
    """, {"po_names": po_names}, as_dict=True)
    
    # Group by PO and calculate totals
    for inv in invoices:
        po = inv["purchase_order"]
        
        if po not in invoice_data:
            invoice_data[po] = {
                'invoiced_amount': 0,
                'vat_amount': 0,
                'total_with_vat': 0
            }
        
        # If invoice has taxes (VAT), use tax amount, otherwise 0
        vat = flt(inv["tax_amount"]) if inv["tax_amount"] else 0
        
        invoice_data[po]['invoiced_amount'] += flt(inv["net_total"])
        invoice_data[po]['vat_amount'] += vat
        invoice_data[po]['total_with_vat'] += flt(inv["grand_total"])
    
    return invoice_data


def _get_paid_map_via_gl(po_names):
    """
    Get paid amounts by querying GL Entry table directly.
    This captures ALL payments regardless of source.
    """
    if not po_names:
        return {}
    
    paid_map = {}
    
    # Get all invoices linked to POs
    invoice_to_po = {}
    inv_rows = frappe.db.sql("""
        SELECT DISTINCT pii.parent AS invoice, pii.purchase_order
        FROM `tabPurchase Invoice Item` pii
        INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.docstatus = 1 
          AND pii.purchase_order IN %(po_names)s
    """, {"po_names": po_names}, as_dict=True)
    
    for r in inv_rows:
        invoice_to_po[r["invoice"]] = r["purchase_order"]
    
    all_references = list(po_names) + list(invoice_to_po.keys())
    
    if not all_references:
        return {}
    
    # Query GL Entry for credit entries (payments)
    gl_entries = frappe.db.sql("""
        SELECT
            voucher_type as against_voucher_type,
            voucher_no as against_voucher_no,
            SUM(credit_in_account_currency) as total_credit
        FROM `tabGL Entry`
        WHERE docstatus = 1
          AND voucher_type IN ('Purchase Order', 'Purchase Invoice')
          AND voucher_no IN %(references)s
          AND credit_in_account_currency > 0
        GROUP BY voucher_type, voucher_no
    """, {"references": all_references}, as_dict=True)
    
    # Map payments to POs
    for entry in gl_entries:
        if entry['against_voucher_type'] == 'Purchase Order':
            po = entry['against_voucher_no']
            paid_map[po] = flt(paid_map.get(po, 0)) + flt(entry['total_credit'])
        
        elif entry['against_voucher_type'] == 'Purchase Invoice':
            invoice = entry['against_voucher_no']
            po = invoice_to_po.get(invoice)
            if po:
                paid_map[po] = flt(paid_map.get(po, 0)) + flt(entry['total_credit'])
    
    return paid_map


def _convert_to_sar(amount, from_currency, to_currency, posting_date):
    """
    Convert amount from PO currency to SAR (or company default currency).
    If currencies are same, return original amount.
    """
    if not amount or from_currency == to_currency:
        return amount
    
    # Get exchange rate
    exchange_rate = frappe.db.get_value("Currency Exchange", 
        {"from_currency": from_currency, "to_currency": to_currency, "date": ["<=", posting_date]},
        "exchange_rate", order_by="date desc")
    
    if not exchange_rate:
        # Fallback to current exchange rate
        exchange_rate = frappe.db.get_value("Currency Exchange",
            {"from_currency": from_currency, "to_currency": to_currency},
            "exchange_rate")
    
    if exchange_rate:
        return amount * exchange_rate
    
    # If no exchange rate found, return original amount with warning
    # frappe.msgprint(_("No exchange rate found for {0} to {1}").format(from_currency, to_currency), alert=True)
    return amount