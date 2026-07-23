"""
PO Payment Status Report
Shows Purchase Orders with Invoice Amount, Paid Amount, and Pending Amount.

Filters: Company, From Date, To Date, Supplier, Supplier Group, Purchase Order
Option to group by month like trial balance

Payment sources captured:
  A. Payment Entry -> PO reference    : allocated_amount from tabPayment Entry Reference
                                        (exact, no ratio needed)
  B. Payment Entry -> PI reference    : allocated_amount x PO's proportional share of
                                        that invoice (item-line base_amount ratio)
  C. Journal Entry -> Purchase Invoice: Payment recorded in Journal Entry with PI reference
                                        in the reference field or through account mapping
  D. Journal Entry -> Purchase Order  : GL debit on AP account, direct
  E. Journal Entry -> Payment         : Journal Entry linked to Payment Entry

Shared-invoice handling:
  When a single Purchase Invoice covers items from more than one PO, each PO
  receives only its proportional share based on item-line base_amount.

Month grouping (NEW):
  When the "group_by_month" filter is enabled, rows are grouped into
  month-total rows followed by their detail rows, plus a grand total row.
  Grouping rows are marked with clean boolean flags (is_month_total /
  is_grand_total) rather than mutating the purchase_order field, so the
  PO name always stays a valid, clickable value (needed for the client-side
  "PO Summary" popup button) and totals are computed only from real rows.
"""

import frappe
from frappe import _
from frappe.utils import flt, getdate


def execute(filters=None):
	filters = filters or {}
	columns = get_columns(filters)
	data = get_data(filters)

	if filters.get("group_by_month"):
		data = group_by_month(data)

	return columns, data


def get_columns(filters=None):
	columns = [
		{
			"label": _("Month"),
			"fieldname": "month",
			"fieldtype": "Data",
			"width": 120,
		},
		{
			"label": _("Purchase Order"),
			"fieldname": "purchase_order",
			"fieldtype": "Link",
			"options": "Purchase Order",
			"width": 180,
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
			"label": _("Status"),
			"fieldname": "status",
			"fieldtype": "Data",
			"width": 110,
		},
		{
			"label": _("PO Amount (PO Currency)"),
			"fieldname": "po_amount",
			"fieldtype": "Currency",
			"options": "po_currency",
			"width": 130,
		},
	]

	if filters.get("show_vat"):
		columns.extend([
			{
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
			},
		])

	columns.extend([
		{
			"label": _("Invoiced Amount"),
			"fieldname": "total_invoice_with_vat",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"label": _("PO Amount Yet to Be Invoiced (SAR)"),
			"fieldname": "yet_to_be_invoiced",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
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
			"width": 130,
		},
		{
			"label": _("Outstanding Amount (SAR)"),
			"fieldname": "outstanding_amount",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		},
		{
			"label": _("PO Currency"),
			"fieldname": "po_currency",
			"fieldtype": "Link",
			"options": "Currency",
			"width": 100,
		},
		
	])

	return columns


def get_data(filters):
	conditions, values = get_conditions(filters)

	# 1. Fetch Purchase Orders
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
			po.status,
			po.custom_closed_manually AS closed_manually
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

	# 2. Company currency
	company_currency = (
		frappe.db.get_value("Company", filters.get("company"), "default_currency") or "SAR"
	)

	# 3. Invoiced amount per PO (proportional for shared invoices)
	invoice_data = _get_invoice_data(po_names, company_currency)

	# 4. Paid amount per PO (Payment Entry + Journal Entry)
	paid_map = _get_paid_map(po_names)

	# 5. Assemble rows
	data = []
	for row in po_list:
		po = row["purchase_order"]
		po_amount = flt(row["po_amount"])

		invoice_info = invoice_data.get(po, {
			"invoiced_amount": 0,
			"vat_amount": 0,
			"total_with_vat": 0,
		})

		invoiced_amount = flt(invoice_info["invoiced_amount"])
		vat_amount = flt(invoice_info["vat_amount"])
		total_invoice_with_vat = flt(invoice_info["total_with_vat"])
		paid_amount = flt(paid_map.get(po, 0))

		po_amount_in_sar = _convert_to_sar(
			po_amount, row["po_currency"], company_currency, row["transaction_date"]
		)

		yet_to_be_invoiced = max(po_amount_in_sar - total_invoice_with_vat, 0)
		paid_vs_invoiced = paid_amount - total_invoice_with_vat
		outstanding_amount = max(po_amount_in_sar - paid_amount, 0)

		if float(f"{paid_amount:.2f}") >= float(f"{po_amount_in_sar:.2f}"):
			display_status = "Fully Paid"
		elif paid_amount > 0:
			display_status = "Partially Paid"
		else:
			display_status = "Not Paid"

		# NEW: manual close override — only applies if not already Fully Paid
		if row.get("closed_manually") and display_status != "Fully Paid":
			display_status = "Closed Manually"

		month = getdate(row["transaction_date"]).strftime("%b %Y") if row["transaction_date"] else ""
		month_key = getdate(row["transaction_date"]).strftime("%Y%m") if row["transaction_date"] else ""

		data.append({
			"purchase_order": po,
			"transaction_date": row["transaction_date"],
			"supplier": row["supplier"],
			"supplier_name": row["supplier_name"],
			"supplier_group": row["supplier_group"],
			"company": row["company"],
			"po_currency": row["po_currency"],
			"po_amount": po_amount,
			"po_amount_sar": po_amount_in_sar,
			"invoiced_amount": invoiced_amount,
			"vat_amount": vat_amount,
			"total_invoice_with_vat": total_invoice_with_vat,
			"yet_to_be_invoiced": yet_to_be_invoiced,
			"paid_amount": paid_amount,
			"outstanding_amount": outstanding_amount,
			"status": display_status,
			"paid_vs_invoiced": paid_vs_invoiced,
			"currency": company_currency,
			"month": month,
			"month_key": month_key,
		})

	if filters.get("status"):
		print(str(filters.get("status")))
		data = [d for d in data if d["status"] in filters["status"]]

	return data


def group_by_month(data):
	"""
	Groups PO data by month (trial-balance style): a bold month-total row
	followed by its detail rows, then a grand total row at the end.

	Grouping rows carry clean flags instead of mutated text:
	  - is_month_total / is_grand_total: booleans for styling/filtering
	  - label: display text for the (otherwise empty) purchase_order column

	Detail rows are returned unmodified except for an added is_child_row
	flag, so "purchase_order" always remains a real, clickable PO name on
	every non-total row.
	"""
	if not data:
		return []

	SUM_FIELDS = [
		"po_amount", "po_amount_sar", "invoiced_amount", "vat_amount",
		"total_invoice_with_vat", "yet_to_be_invoiced", "paid_amount",
		"paid_vs_invoiced", "outstanding_amount",
	]

	grouped = {}
	order = []

	for row in data:
		month_key = row.get("month_key", "")
		if not month_key:
			continue
		if month_key not in grouped:
			grouped[month_key] = {
				"month": row["month"],
				"rows": [],
				"company": row.get("company"),
				"po_currency": row.get("po_currency"),
				"currency": row.get("currency"),
				**{f: 0 for f in SUM_FIELDS},
			}
			order.append(month_key)

		g = grouped[month_key]
		g["rows"].append(row)
		for f in SUM_FIELDS:
			g[f] += flt(row.get(f, 0))

	result = []
	for month_key in sorted(order):
		g = grouped[month_key]
		total_row = {
			"label": _("{0} \u2014 Total").format(g["month"]),
			"purchase_order": "",
			"month": g["month"],
			"transaction_date": None,
			"supplier": "",
			"supplier_name": "",
			"supplier_group": "",
			"company": g["company"],
			"po_currency": g["po_currency"],
			"currency": g["currency"],
			"status": "Summary",
			"is_month_total": 1,
		}
		for f in SUM_FIELDS:
			total_row[f] = g[f]
		result.append(total_row)

		for child in g["rows"]:
			child["is_child_row"] = 1
			result.append(child)

	grand_row = {
		"label": _("Grand Total"),
		"purchase_order": "",
		"month": "",
		"transaction_date": None,
		"supplier": "",
		"supplier_name": "",
		"supplier_group": "",
		"company": data[0].get("company") if data else "",
		"po_currency": data[0].get("po_currency") if data else "",
		"currency": data[0].get("currency") if data else "SAR",
		"status": "Grand Total",
		"is_grand_total": 1,
	}
	for f in SUM_FIELDS:
		grand_row[f] = sum(flt(r.get(f, 0)) for r in data)
	result.append(grand_row)

	return result


# -----------------------------------------------------------------------------
# Conditions
# -----------------------------------------------------------------------------

def get_conditions(filters):
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


# -----------------------------------------------------------------------------
# Invoice data - proportional allocation for shared invoices
# -----------------------------------------------------------------------------

def _get_invoice_data(po_names, company_currency):
	if not po_names:
		return {}

	invoice_headers = frappe.db.sql("""
		SELECT
			pi.name                          AS invoice,
			pi.base_net_total                AS net_total,
			pi.base_total_taxes_and_charges  AS tax_amount,
			pi.base_grand_total              AS grand_total
		FROM `tabPurchase Invoice` pi
		WHERE pi.docstatus = 1
		  AND pi.name IN (
		      SELECT DISTINCT pii.parent
		      FROM `tabPurchase Invoice Item` pii
		      WHERE pii.purchase_order IN %(po_names)s
		  )
	""", {"po_names": po_names}, as_dict=True)

	header_map = {h["invoice"]: h for h in invoice_headers}
	if not header_map:
		return {}

	all_invoices = list(header_map.keys())

	item_lines = frappe.db.sql("""
		SELECT
			pii.parent           AS invoice,
			pii.purchase_order   AS po,
			SUM(pii.base_amount) AS po_line_total
		FROM `tabPurchase Invoice Item` pii
		WHERE pii.parent IN %(invoices)s
		  AND pii.purchase_order IN %(po_names)s
		GROUP BY pii.parent, pii.purchase_order
	""", {"invoices": all_invoices, "po_names": po_names}, as_dict=True)

	invoice_full_totals = frappe.db.sql("""
		SELECT
			pii.parent           AS invoice,
			SUM(pii.base_amount) AS full_line_total
		FROM `tabPurchase Invoice Item` pii
		WHERE pii.parent IN %(invoices)s
		GROUP BY pii.parent
	""", {"invoices": all_invoices}, as_dict=True)

	full_total_map = {r["invoice"]: flt(r["full_line_total"]) for r in invoice_full_totals}

	invoice_data = {}
	for line in item_lines:
		inv = line["invoice"]
		po = line["po"]
		po_share = flt(line["po_line_total"])

		header = header_map.get(inv, {})
		full_total = full_total_map.get(inv, 0)
		if not full_total:
			continue

		ratio = po_share / full_total
		net_total = flt(header.get("net_total", 0))
		tax_amount = flt(header.get("tax_amount", 0))
		grand_total = flt(header.get("grand_total", 0))

		if po not in invoice_data:
			invoice_data[po] = {"invoiced_amount": 0, "vat_amount": 0, "total_with_vat": 0}

		invoice_data[po]["invoiced_amount"] += net_total * ratio
		invoice_data[po]["vat_amount"] += tax_amount * ratio
		invoice_data[po]["total_with_vat"] += grand_total * ratio

	return invoice_data


# -----------------------------------------------------------------------------
# Paid amounts - Payment Entry + Journal Entry
# -----------------------------------------------------------------------------

def _get_paid_map(po_names):
	if not po_names:
		return {}

	paid_map = {}

	inv_rows = frappe.db.sql("""
		SELECT
			pii.parent           AS invoice,
			pii.purchase_order   AS po,
			SUM(pii.base_amount) AS po_line_total
		FROM `tabPurchase Invoice Item` pii
		INNER JOIN `tabPurchase Invoice` pi ON pi.name = pii.parent
		WHERE pi.docstatus = 1
		  AND pii.purchase_order IN %(po_names)s
		GROUP BY pii.parent, pii.purchase_order
	""", {"po_names": po_names}, as_dict=True)

	all_invoices = list({r["invoice"] for r in inv_rows}) if inv_rows else []

	invoice_po_ratio = {}
	if all_invoices:
		full_totals = frappe.db.sql("""
			SELECT
				pii.parent           AS invoice,
				SUM(pii.base_amount) AS full_line_total
			FROM `tabPurchase Invoice Item` pii
			WHERE pii.parent IN %(invoices)s
			GROUP BY pii.parent
		""", {"invoices": all_invoices}, as_dict=True)

		full_total_map = {r["invoice"]: flt(r["full_line_total"]) for r in full_totals}

		for r in inv_rows:
			denom = full_total_map.get(r["invoice"], 0)
			invoice_po_ratio[(r["invoice"], r["po"])] = (
				flt(r["po_line_total"]) / denom if denom else 0
			)

	# Source A: Payment Entry -> Purchase Order reference
	pe_po_refs = frappe.db.sql("""
		SELECT
			per.reference_name        AS purchase_order,
			SUM(per.allocated_amount) AS paid
		FROM `tabPayment Entry Reference` per
		INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
		WHERE pe.docstatus = 1
		  AND per.reference_doctype = 'Purchase Order'
		  AND per.reference_name IN %(po_names)s
		GROUP BY per.reference_name
	""", {"po_names": po_names}, as_dict=True)

	for entry in pe_po_refs:
		po = entry["purchase_order"]
		paid_map[po] = flt(paid_map.get(po, 0)) + flt(entry["paid"])

	# Source B: Payment Entry -> Purchase Invoice reference
	if all_invoices:
		pe_pi_refs = frappe.db.sql("""
			SELECT
				per.reference_name        AS invoice,
				SUM(per.allocated_amount) AS paid
			FROM `tabPayment Entry Reference` per
			INNER JOIN `tabPayment Entry` pe ON pe.name = per.parent
			WHERE pe.docstatus = 1
			  AND per.reference_doctype = 'Purchase Invoice'
			  AND per.reference_name IN %(invoices)s
			GROUP BY per.reference_name
		""", {"invoices": all_invoices}, as_dict=True)

		for entry in pe_pi_refs:
			inv = entry["invoice"]
			paid = flt(entry["paid"])
			for (e_inv, po), ratio in invoice_po_ratio.items():
				if e_inv == inv:
					paid_map[po] = flt(paid_map.get(po, 0)) + paid * ratio

	# Source C: Journal Entry -> Purchase Invoice
	if all_invoices:
		je_pi_gl = frappe.db.sql("""
			SELECT
				gle.against_voucher                AS invoice,
				SUM(gle.debit_in_account_currency) AS paid
			FROM `tabGL Entry` gle
			WHERE gle.docstatus = 1
			  AND gle.is_cancelled = 0
			  AND gle.voucher_type = 'Journal Entry'
			AND gle.voucher_subtype != 'Deferred Expense'
			  AND gle.against_voucher_type = 'Purchase Invoice'
			  AND gle.against_voucher IN %(invoices)s
			  AND gle.debit_in_account_currency > 0
			GROUP BY gle.against_voucher
		""", {"invoices": all_invoices}, as_dict=True)

		je_pi_account = frappe.db.sql("""
			SELECT
				jv.parent                          AS journal_entry,
				jv.reference_name                  AS invoice,
				SUM(jv.debit_in_account_currency)  AS paid
			FROM `tabJournal Entry Account` jv
			INNER JOIN `tabJournal Entry` je ON je.name = jv.parent
			WHERE je.docstatus = 1
			  AND je.voucher_type = 'Journal Entry'
			  AND jv.reference_type = 'Purchase Invoice'
			  AND jv.reference_name IN %(invoices)s
			  AND jv.debit_in_account_currency > 0
			GROUP BY jv.parent, jv.reference_name
		""", {"invoices": all_invoices}, as_dict=True)

		all_je_payments = {}
		for entry in je_pi_gl:
			inv = entry["invoice"]
			all_je_payments[inv] = flt(all_je_payments.get(inv, 0)) + flt(entry["paid"])
		for entry in je_pi_account:
			inv = entry["invoice"]
			all_je_payments[inv] = flt(all_je_payments.get(inv, 0)) + flt(entry["paid"])

		for inv, paid in all_je_payments.items():
			for (e_inv, po), ratio in invoice_po_ratio.items():
				if e_inv == inv:
					paid_map[po] = flt(paid_map.get(po, 0)) + paid * ratio

	# Source D: Journal Entry -> Purchase Order
	je_po = frappe.db.sql("""
		SELECT
			gle.against_voucher                AS purchase_order,
			SUM(gle.debit_in_account_currency) AS paid
		FROM `tabGL Entry` gle
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND gle.voucher_type = 'Journal Entry'
			AND gle.voucher_subtype != 'Deferred Expense'
		  AND gle.against_voucher_type = 'Purchase Order'
		  AND gle.against_voucher IN %(po_names)s
		  AND gle.debit_in_account_currency > 0
		GROUP BY gle.against_voucher
	""", {"po_names": po_names}, as_dict=True)

	for entry in je_po:
		po = entry["purchase_order"]
		paid_map[po] = flt(paid_map.get(po, 0)) + flt(entry["paid"])

	je_po_account = frappe.db.sql("""
		SELECT
			jv.reference_name                 AS purchase_order,
			SUM(jv.debit_in_account_currency) AS paid
		FROM `tabJournal Entry Account` jv
		INNER JOIN `tabJournal Entry` je ON je.name = jv.parent
		WHERE je.docstatus = 1
		  AND je.voucher_type = 'Journal Entry'
		  AND jv.reference_type = 'Purchase Order'
		  AND jv.reference_name IN %(po_names)s
		  AND jv.debit_in_account_currency > 0
		GROUP BY jv.reference_name
	""", {"po_names": po_names}, as_dict=True)

	for entry in je_po_account:
		po = entry["purchase_order"]
		paid_map[po] = flt(paid_map.get(po, 0)) + flt(entry["paid"])

	# Source E: Journal Entry -> Payment Entry
	je_payment_entries = frappe.db.sql("""
		SELECT
			gle.against_voucher                AS payment_entry,
			SUM(gle.debit_in_account_currency) AS paid_amount
		FROM `tabGL Entry` gle
		WHERE gle.docstatus = 1
		  AND gle.is_cancelled = 0
		  AND gle.voucher_type = 'Journal Entry'
									AND gle.voucher_subtype != 'Deferred Expense'
		  AND gle.against_voucher_type = 'Payment Entry'
		  AND gle.debit_in_account_currency > 0
		GROUP BY gle.against_voucher
	""", as_dict=True)

	if je_payment_entries:
		payment_entry_names = [pe["payment_entry"] for pe in je_payment_entries]

		pe_refs = frappe.db.sql("""
			SELECT
				per.parent AS payment_entry,
				per.reference_doctype,
				per.reference_name,
				per.allocated_amount
			FROM `tabPayment Entry Reference` per
			WHERE per.parent IN %(payment_entries)s
			  AND per.docstatus = 1
			  AND per.reference_doctype IN ('Purchase Order', 'Purchase Invoice')
		""", {"payment_entries": payment_entry_names}, as_dict=True)

		payment_refs_map = {}
		for ref in pe_refs:
			payment_refs_map.setdefault(ref["payment_entry"], []).append(ref)

		for je_payment in je_payment_entries:
			pe_name = je_payment["payment_entry"]
			je_amount = flt(je_payment["paid_amount"])

			refs = payment_refs_map.get(pe_name, [])
			total_allocated = sum(flt(ref["allocated_amount"]) for ref in refs)

			if total_allocated > 0:
				for ref in refs:
					ref_amount = flt(ref["allocated_amount"])
					ref_doctype = ref["reference_doctype"]
					ref_name = ref["reference_name"]

					proportion = ref_amount / total_allocated
					allocated_je_amount = je_amount * proportion

					if ref_doctype == "Purchase Order":
						paid_map[ref_name] = flt(paid_map.get(ref_name, 0)) + allocated_je_amount
					elif ref_doctype == "Purchase Invoice":
						for (inv, po), ratio in invoice_po_ratio.items():
							if inv == ref_name:
								paid_map[po] = flt(paid_map.get(po, 0)) + allocated_je_amount * ratio

	return paid_map


# -----------------------------------------------------------------------------
# Currency conversion
# -----------------------------------------------------------------------------

def _convert_to_sar(amount, from_currency, to_currency, posting_date):
	if not amount or from_currency == to_currency:
		return amount

	exchange_rate = frappe.db.get_value(
		"Currency Exchange",
		{"from_currency": from_currency, "to_currency": to_currency, "date": ["<=", posting_date]},
		"exchange_rate",
		order_by="date desc",
	)

	if not exchange_rate:
		exchange_rate = frappe.db.get_value(
			"Currency Exchange",
			{"from_currency": from_currency, "to_currency": to_currency},
			"exchange_rate",
		)

	return amount * exchange_rate if exchange_rate else amount