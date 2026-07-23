# Copyright (c) 2026, HM
# Shared engine for Customer / Supplier Statement of Account.
# Single source of truth used by both Script Reports and the IFRS print API.

import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate, add_days, nowdate


def get_party_config(party_type):
	"""Sign convention per IFRS presentation:
	Trade Receivables (Customer): balance = Dr - Cr (debit-nature asset)
	Trade Payables  (Supplier): balance = Cr - Dr (credit-nature liability)
	"""
	if party_type == "Customer":
		return {
			"party_type": "Customer",
			"party_field": "customer_name",
			"invoice_doctype": "Sales Invoice",
			"sign": 1,
			"ifrs_caption": _("Trade and Other Receivables (IAS 1.54h / IFRS 9)"),
		}
	return {
		"party_type": "Supplier",
		"party_field": "supplier_name",
		"invoice_doctype": "Purchase Invoice",
		"sign": -1,
		"ifrs_caption": _("Trade and Other Payables (IAS 1.54k / IFRS 9)"),
	}


def get_opening_balance(party_type, party, company, from_date, open_refs=None):
	cfg = get_party_config(party_type)
	if open_refs is None:
		row = frappe.db.sql(
			"""
			SELECT COALESCE(SUM(debit - credit), 0) AS bal
			FROM `tabGL Entry`
			WHERE party_type = %s AND party = %s AND company = %s
				AND posting_date < %s AND is_cancelled = 0
			""",
			(party_type, party, company, from_date),
		)
		return flt(row[0][0]) * cfg["sign"] if row else 0.0

	# Open-items mode: opening = pre-period movement of still-open references
	# only, so that Opening + shown transactions ties exactly to Outstanding.
	if not open_refs:
		return 0.0
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(gle.against_voucher, ''), gle.voucher_no) AS ref,
			SUM(gle.debit - gle.credit) AS net
		FROM `tabGL Entry` gle
		WHERE gle.party_type = %s AND gle.party = %s AND gle.company = %s
			AND gle.posting_date < %s AND gle.is_cancelled = 0
		GROUP BY ref
		""",
		(party_type, party, company, from_date),
		as_dict=True,
	)
	return sum(flt(r.net) for r in rows if r.ref in open_refs) * cfg["sign"]


def get_open_refs(party_type, party, company, as_on):
	"""References (invoices / standalone vouchers) NOT fully reconciled as on date.

	A reference is 'reconciled' when its GL net (grouped by against_voucher,
	falling back to voucher_no) is ~0, i.e. fully knocked off by payments,
	credit/debit notes or JE allocations.
	"""
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(gle.against_voucher, ''), gle.voucher_no) AS ref
		FROM `tabGL Entry` gle
		WHERE gle.party_type = %s AND gle.party = %s AND gle.company = %s
			AND gle.posting_date <= %s AND gle.is_cancelled = 0
		GROUP BY ref
		HAVING ABS(SUM(gle.debit - gle.credit)) > 0.005
		""",
		(party_type, party, company, as_on),
	)
	return {r[0] for r in rows}


def get_transactions(party_type, party, company, from_date, to_date, open_refs=None):
	cfg = get_party_config(party_type)
	entries = frappe.db.sql(
		"""
		SELECT
			gle.posting_date, gle.voucher_type, gle.voucher_no,
			gle.debit, gle.credit, gle.against, gle.remarks,
			gle.against_voucher_type, gle.against_voucher
		FROM `tabGL Entry` gle
		WHERE gle.party_type = %s AND gle.party = %s AND gle.company = %s
			AND gle.posting_date BETWEEN %s AND %s
			AND gle.is_cancelled = 0
		ORDER BY gle.posting_date, gle.creation
		""",
		(party_type, party, company, from_date, to_date),
		as_dict=True,
	)

	if open_refs is not None:
		# Open-items mode: keep only entries whose reference chain is still
		# unreconciled as on to_date (fully knocked-off vouchers are hidden)
		entries = [
			e for e in entries
			if (e.against_voucher or e.voucher_no) in open_refs
		]

	rows = []
	balance = get_opening_balance(
		party_type, party, company, from_date,
		open_refs=open_refs,
	)

	for e in entries:
		amount = flt(e.debit) - flt(e.credit)
		balance += amount * cfg["sign"]
		# For a customer: debit increases receivable (charges), credit reduces it (receipts/credits)
		# For a supplier: credit increases payable (charges), debit reduces it (payments/debits)
		charge = flt(e.debit) if cfg["sign"] == 1 else flt(e.credit)
		settlement = flt(e.credit) if cfg["sign"] == 1 else flt(e.debit)
		rows.append(
			frappe._dict(
				posting_date=e.posting_date,
				voucher_type=e.voucher_type,
				voucher_no=e.voucher_no,
				reference=e.against_voucher or "",
				remarks=(e.remarks or "").replace("\n", " ")[:140],
				charge=charge,
				settlement=settlement,
				balance=balance,
			)
		)
	return rows


def get_ageing(party_type, party, company, as_on):
	"""Ageing of open vouchers as on date, from Payment Ledger-free GL netting
	per against_voucher. Buckets: Current(0-30), 31-60, 61-90, 91-120, 120+."""
	cfg = get_party_config(party_type)
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(NULLIF(gle.against_voucher, ''), gle.voucher_no) AS ref,
			MIN(gle.posting_date) AS ref_date,
			SUM(gle.debit - gle.credit) AS net
		FROM `tabGL Entry` gle
		WHERE gle.party_type = %s AND gle.party = %s AND gle.company = %s
			AND gle.posting_date <= %s AND gle.is_cancelled = 0
		GROUP BY ref
		HAVING ABS(SUM(gle.debit - gle.credit)) > 0.005
		""",
		(party_type, party, company, as_on),
		as_dict=True,
	)

	buckets = {"b0": 0.0, "b1": 0.0, "b2": 0.0, "b3": 0.0, "b4": 0.0}
	as_on = getdate(as_on)
	for r in rows:
		outstanding = flt(r.net) * cfg["sign"]
		age = (as_on - getdate(r.ref_date)).days
		if age <= 30:
			buckets["b0"] += outstanding
		elif age <= 60:
			buckets["b1"] += outstanding
		elif age <= 90:
			buckets["b2"] += outstanding
		elif age <= 120:
			buckets["b3"] += outstanding
		else:
			buckets["b4"] += outstanding
	buckets["total"] = sum(buckets.values())
	return buckets


def get_statement_data(party_type, party, company, from_date, to_date, hide_reconciled=0):
	cfg = get_party_config(party_type)
	open_refs = (
		get_open_refs(party_type, party, company, to_date)
		if frappe.utils.cint(hide_reconciled)
		else None
	)
	opening = get_opening_balance(party_type, party, company, from_date, open_refs=open_refs)
	rows = get_transactions(party_type, party, company, from_date, to_date, open_refs=open_refs)
	total_charges = sum(r.charge for r in rows)
	total_settlements = sum(r.settlement for r in rows)
	closing = rows[-1].balance if rows else opening
	ageing = get_ageing(party_type, party, company, to_date)

	party_doc = frappe.db.get_value(
		party_type, party,
		[cfg["party_field"] + " as party_name", "tax_id"],
		as_dict=True,
	) or frappe._dict(party_name=party, tax_id="")

	company_doc = frappe.db.get_value(
		"Company", company,
		["company_name", "tax_id", "default_currency", "country"],
		as_dict=True,
	)

	return frappe._dict(
		config=cfg,
		party=party,
		party_name=party_doc.party_name or party,
		party_tax_id=party_doc.tax_id or "",
		company=company,
		company_tax_id=(company_doc.tax_id or "") if company_doc else "",
		currency=(company_doc.default_currency or "SAR") if company_doc else "SAR",
		from_date=from_date,
		to_date=to_date,
		opening_balance=opening,
		rows=rows,
		total_charges=total_charges,
		total_settlements=total_settlements,
		closing_balance=closing,
		ageing=ageing,
		hide_reconciled=frappe.utils.cint(hide_reconciled),
	)
