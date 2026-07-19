# Copyright (c) 2026, HM

import frappe
from frappe import _
from gicore.gi_accounting.api.statement_engine import get_statement_data


def execute(filters=None):
	return run(filters, "Customer")


def run(filters, party_type):
	filters = frappe._dict(filters or {})
	party_key = party_type.lower()
	if not filters.get(party_key):
		frappe.throw(_("Please select a {0}").format(_(party_type)))

	data = get_statement_data(
		party_type, filters.get(party_key), filters.company,
		filters.from_date, filters.to_date,
		hide_reconciled=filters.get("hide_reconciled") or 0,
	)

	charge_label = _("Charges (Dr)") if party_type == "Customer" else _("Charges (Cr)")
	settle_label = _("Receipts / Credits") if party_type == "Customer" else _("Payments / Debits")

	columns = [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 130},
		{"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link", "options": "voucher_type", "width": 170},
		{"label": _("Reference"), "fieldname": "reference", "fieldtype": "Data", "width": 140},
		{"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 220},
		{"label": charge_label, "fieldname": "charge", "fieldtype": "Currency", "width": 130},
		{"label": settle_label, "fieldname": "settlement", "fieldtype": "Currency", "width": 130},
		{"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 140},
	]

	rows = [{
		"posting_date": data.from_date,
		"voucher_type": "",
		"voucher_no": "",
		"remarks": _("Opening Balance"),
		"charge": None,
		"settlement": None,
		"balance": data.opening_balance,
	}]
	rows += [dict(r) for r in data.rows]
	rows.append({
		"posting_date": data.to_date,
		"remarks": _("Closing Balance"),
		"charge": data.total_charges,
		"settlement": data.total_settlements,
		"balance": data.closing_balance,
	})

	a = data.ageing
	message = _(
		"Ageing as on {0} — Current (0-30): {1} | 31-60: {2} | 61-90: {3} | 91-120: {4} | 120+: {5} | Total Outstanding: {6}"
	).format(
		frappe.utils.formatdate(data.to_date),
		frappe.utils.fmt_money(a["b0"], currency=data.currency),
		frappe.utils.fmt_money(a["b1"], currency=data.currency),
		frappe.utils.fmt_money(a["b2"], currency=data.currency),
		frappe.utils.fmt_money(a["b3"], currency=data.currency),
		frappe.utils.fmt_money(a["b4"], currency=data.currency),
		frappe.utils.fmt_money(a["total"], currency=data.currency),
	)
	if data.hide_reconciled:
		message = _("Open Items only — fully reconciled transactions are hidden. ") + message

	return columns, rows, message
