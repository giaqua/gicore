import frappe
from frappe import _


@frappe.whitelist()
def reconcile_payment_entries(invoice, payments):
    if isinstance(payments, str):
        payments = frappe.parse_json(payments)

    si = frappe.get_doc("Sales Invoice", invoice)
    if si.docstatus != 1:
        frappe.throw(_("Invoice must be submitted"))

    pr = frappe.new_doc("Payment Reconciliation")
    pr.company = si.company
    pr.party_type = "Customer"
    pr.party = si.customer
    pr.receivable_payable_account = si.debit_to
    pr.get_unreconciled_entries()  # populates pr.invoices and pr.payments

    invoice_row = next((r for r in pr.invoices if r.invoice_number == si.name), None)
    if not invoice_row:
        frappe.throw(_("Invoice {0} not found in unreconciled entries").format(si.name))

    pr.allocation = []
    for p in payments:
        pay_row = next((r for r in pr.payments if r.reference_name == p["payment_entry"]), None)
        if not pay_row:
            frappe.throw(_("Payment Entry {0} not found in unreconciled entries").format(p["payment_entry"]))

        pr.append("allocation", {
            "reference_type": pay_row.reference_type,
            "reference_name": pay_row.reference_name,
            "reference_row": pay_row.get("reference_row"),
            "invoice_type": invoice_row.invoice_type,
            "invoice_number": invoice_row.invoice_number,
            "unreconciled_amount": pay_row.amount,
            "amount": p["amount"],
            "allocated_amount": p["amount"],
            "difference_amount": 0,
            "currency": pay_row.get("currency"),
            "exchange_rate": pay_row.get("exchange_rate", 1),
        })

    pr.reconcile()
    return {"status": "success"}


@frappe.whitelist()
def reconcile_purchase_payment_entries(invoice, payments):
    if isinstance(payments, str):
        payments = frappe.parse_json(payments)

    pi = frappe.get_doc("Purchase Invoice", invoice)
    if pi.docstatus != 1:
        frappe.throw(_("Invoice must be submitted"))

    pr = frappe.new_doc("Payment Reconciliation")
    pr.company = pi.company
    pr.party_type = "Supplier"
    pr.party = pi.supplier
    pr.receivable_payable_account = pi.credit_to
    pr.get_unreconciled_entries()

    invoice_row = next((r for r in pr.invoices if r.invoice_number == pi.name), None)
    if not invoice_row:
        frappe.throw(_("Invoice {0} not found in unreconciled entries").format(pi.name))

    pr.allocation = []
    for p in payments:
        pay_row = next((r for r in pr.payments if r.reference_name == p["payment_entry"]), None)
        if not pay_row:
            frappe.throw(_("Payment Entry {0} not found in unreconciled entries").format(p["payment_entry"]))

        pr.append("allocation", {
            "reference_type": pay_row.reference_type,
            "reference_name": pay_row.reference_name,
            "reference_row": pay_row.get("reference_row"),
            "invoice_type": invoice_row.invoice_type,
            "invoice_number": invoice_row.invoice_number,
            "unreconciled_amount": pay_row.amount,
            "amount": p["amount"],
            "allocated_amount": p["amount"],
            "difference_amount": 0,
            "currency": pay_row.get("currency"),
            "exchange_rate": pay_row.get("exchange_rate", 1),
        })

    pr.reconcile()
    return {"status": "success"}