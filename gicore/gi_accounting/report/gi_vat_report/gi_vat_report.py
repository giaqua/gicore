import frappe
from frappe import _
from frappe.utils import flt, getdate, formatdate, nowdate, now_datetime
import json


def execute(filters=None):
	"""Main entry point for GI VAT Report."""
	_log_report_run(filters)

	columns = get_columns(filters)
	data = get_data(filters)
	chart = get_chart(data, filters)
	report_summary = get_report_summary(data, filters)

	return columns, data, None, chart, report_summary


# ─────────────────────────────────────────────
# COLUMNS
# ─────────────────────────────────────────────

def get_columns(filters):
	mode = (filters or {}).get("report_mode", "Summary")

	if mode == "Summary":
		return [
			{"label": _("VAT Category"),        "fieldname": "vat_category",   "fieldtype": "Data",     "width": 200},
			{"label": _("Description (EN)"),     "fieldname": "description_en", "fieldtype": "Data",     "width": 220},
			{"label": _("Description (AR)"),     "fieldname": "description_ar", "fieldtype": "Data",     "width": 220},
			{"label": _("Taxable Amount (SAR)"), "fieldname": "taxable_amount", "fieldtype": "Currency", "width": 160},
			{"label": _("VAT Amount (SAR)"),     "fieldname": "vat_amount",     "fieldtype": "Currency", "width": 160},
		]
	else:
		return [
			{"label": _("Posting Date"),         "fieldname": "posting_date",   "fieldtype": "Date",         "width": 100},
			{"label": _("Document Type"),         "fieldname": "doctype_label",  "fieldtype": "Data",         "width": 120},
			{"label": _("Document No."),          "fieldname": "name",           "fieldtype": "Dynamic Link", "options": "doctype_name", "width": 160},
			{"label": _("Party"),                 "fieldname": "party",          "fieldtype": "Data",         "width": 180},
			{"label": _("VAT Number (Party)"),    "fieldname": "tax_id",         "fieldtype": "Data",         "width": 140},
			{"label": _("VAT Category"),          "fieldname": "vat_category",   "fieldtype": "Data",         "width": 160},
			{"label": _("Taxable Amount (SAR)"),  "fieldname": "taxable_amount", "fieldtype": "Currency",     "width": 140},
			{"label": _("VAT Rate %"),            "fieldname": "vat_rate",       "fieldtype": "Percent",      "width": 90},
			{"label": _("VAT Amount (SAR)"),      "fieldname": "vat_amount",     "fieldtype": "Currency",     "width": 140},
			{"label": _("Total (SAR)"),           "fieldname": "total",          "fieldtype": "Currency",     "width": 140},
			{"label": _("Currency"),              "fieldname": "currency",       "fieldtype": "Data",         "width": 70},
		]


# ─────────────────────────────────────────────
# DATA
# ─────────────────────────────────────────────

def get_data(filters):
	filters = filters or {}
	mode = filters.get("report_mode", "Summary")

	from_date = filters.get("from_date") or frappe.utils.get_first_day(nowdate())
	to_date   = filters.get("to_date")   or frappe.utils.get_last_day(nowdate())
	company   = filters.get("company")   or frappe.defaults.get_user_default("Company")

	sales_rows    = _get_sales_rows(from_date, to_date, company, filters)
	purchase_rows = _get_purchase_rows(from_date, to_date, company, filters)

	if mode == "Summary":
		return _build_summary(sales_rows, purchase_rows)
	else:
		return _build_detail(sales_rows, purchase_rows)


def _get_sales_rows(from_date, to_date, company, filters):
	"""Fetch Sales Invoice rows with VAT tax lines."""
	conditions = _common_conditions("si", from_date, to_date, company)
	tax_account_condition = _tax_account_condition(filters, "stc")

	rows = frappe.db.sql(f"""
		SELECT
			si.name,
			si.posting_date,
			si.customer        AS party,
			si.tax_id,
			si.currency,
			si.net_total       AS taxable_amount,
			stc.rate           AS vat_rate,
			stc.tax_amount     AS vat_amount,
			(si.net_total + stc.tax_amount) AS total,
			'Sales Invoice'    AS doctype_name,
			'Sales Invoice'    AS doctype_label,
			si.is_return
		FROM `tabSales Invoice` si
		INNER JOIN `tabSales Taxes and Charges` stc
			ON stc.parent = si.name
			AND stc.charge_type IN ('On Net Total', 'Actual')
			{tax_account_condition}
		WHERE {conditions}
		  AND si.docstatus = 1
		ORDER BY si.posting_date, si.name
	""", as_dict=True)

	for r in rows:
		r["section"]      = "sales"
		r["vat_category"] = _classify_vat_sales(r)
	return rows


def _get_purchase_rows(from_date, to_date, company, filters):
	"""Fetch Purchase Invoice rows with VAT tax lines."""
	conditions = _common_conditions("pi", from_date, to_date, company)
	tax_account_condition = _tax_account_condition(filters, "ptc")

	rows = frappe.db.sql(f"""
		SELECT
			pi.name,
			pi.posting_date,
			pi.supplier        AS party,
			pi.tax_id,
			pi.currency,
			pi.net_total       AS taxable_amount,
			ptc.rate           AS vat_rate,
			ptc.tax_amount     AS vat_amount,
			(pi.net_total + ptc.tax_amount) AS total,
			'Purchase Invoice' AS doctype_name,
			'Purchase Invoice' AS doctype_label,
			pi.is_return
		FROM `tabPurchase Invoice` pi
		INNER JOIN `tabPurchase Taxes and Charges` ptc
			ON ptc.parent = pi.name
			AND ptc.charge_type IN ('On Net Total', 'Actual')
			{tax_account_condition}
		WHERE {conditions}
		  AND pi.docstatus = 1
		ORDER BY pi.posting_date, pi.name
	""", as_dict=True)

	for r in rows:
		r["section"]      = "purchases"
		r["vat_category"] = _classify_vat_purchase(r)
	return rows


def _common_conditions(alias, from_date, to_date, company):
	return f"""
		{alias}.company = {frappe.db.escape(company)}
		AND {alias}.posting_date BETWEEN {frappe.db.escape(from_date)} AND {frappe.db.escape(to_date)}
	"""


def _tax_account_condition(filters, alias):
	tax_account = (filters or {}).get("tax_account")
	if tax_account:
		return f"AND {alias}.account_head = {frappe.db.escape(tax_account)}"
	return ""


def _classify_vat_sales(row):
	rate = flt(row.get("vat_rate"))
	is_return = row.get("is_return")
	if rate == 15:
		return "Credit Note (Sales Returns)" if is_return else "Standard Rated Sales (15%)"
	elif rate == 0:
		return "Zero Rated Sales (0%)"
	elif rate is None or rate == "":
		return "Exempt Sales"
	else:
		return f"Other Sales ({rate}%)"


def _classify_vat_purchase(row):
	rate = flt(row.get("vat_rate"))
	is_return = row.get("is_return")
	if rate == 15:
		return "Debit Note (Purchase Returns)" if is_return else "Standard Rated Purchases (15%)"
	elif rate == 0:
		return "Zero Rated Purchases (0%)"
	elif rate is None or rate == "":
		return "Blocked / Exempt Purchases"
	else:
		return f"Other Purchases ({rate}%)"


# ─────────────────────────────────────────────
# SUMMARY BUILD
# ─────────────────────────────────────────────

_SALES_CATS = [
	("Standard Rated Sales (15%)",  "المبيعات الخاضعة للضريبة بنسبة ١٥٪",  "Box 1"),
	("Zero Rated Sales (0%)",        "المبيعات الخاضعة للضريبة بنسبة صفر",  "Box 2"),
	("Exempt Sales",                 "المبيعات المعفاة",                       "Box 3"),
	("Credit Note (Sales Returns)",  "إشعارات الدائن (مردودات المبيعات)",    "Box 4"),
	("Other Sales",                  "مبيعات أخرى",                           "Box 5"),
]

_PURCHASE_CATS = [
	("Standard Rated Purchases (15%)", "المشتريات الخاضعة للضريبة بنسبة ١٥٪", "Box 6"),
	("Zero Rated Purchases (0%)",      "المشتريات بنسبة صفر",                   "Box 7"),
	("Blocked / Exempt Purchases",     "المشتريات المحجوبة / المعفاة",          "Box 8"),
	("Debit Note (Purchase Returns)",  "إشعارات المدين (مردودات المشتريات)",   "Box 9"),
	("Other Purchases",                "مشتريات أخرى",                          "Box 10"),
]


def _build_summary(sales_rows, purchase_rows):
	def aggregate(rows, cats):
		buckets = {c[0]: {"taxable": 0.0, "vat": 0.0} for c in cats}
		for r in rows:
			cat = r.get("vat_category", "")
			matched = cat if cat in buckets else next(
				(k for k in buckets if cat.startswith(k.split("(")[0].strip())), None
			)
			if matched:
				buckets[matched]["taxable"] += flt(r.get("taxable_amount"))
				buckets[matched]["vat"]     += flt(r.get("vat_amount"))
		return buckets

	s_buckets = aggregate(sales_rows,    _SALES_CATS)
	p_buckets = aggregate(purchase_rows, _PURCHASE_CATS)

	data = []

	data.append({"vat_category": "━━ SALES (OUTPUT VAT) ━━", "description_en": "", "description_ar": "ضريبة المخرجات", "taxable_amount": None, "vat_amount": None, "is_group": 1})
	for cat, ar, box in _SALES_CATS:
		b = s_buckets.get(cat, {"taxable": 0.0, "vat": 0.0})
		data.append({
			"vat_category":   f"{box} – {cat}",
			"description_en": cat,
			"description_ar": ar,
			"taxable_amount": b["taxable"],
			"vat_amount":     b["vat"],
		})

	s_taxable = sum(s_buckets[c[0]]["taxable"] for c in _SALES_CATS)
	s_vat     = sum(s_buckets[c[0]]["vat"]     for c in _SALES_CATS)
	data.append({"vat_category": "TOTAL OUTPUT VAT", "description_en": "Total Output VAT", "description_ar": "إجمالي ضريبة المخرجات", "taxable_amount": s_taxable, "vat_amount": s_vat, "is_total": 1})
	data.append({})

	data.append({"vat_category": "━━ PURCHASES (INPUT VAT) ━━", "description_en": "", "description_ar": "ضريبة المدخلات", "taxable_amount": None, "vat_amount": None, "is_group": 1})
	for cat, ar, box in _PURCHASE_CATS:
		b = p_buckets.get(cat, {"taxable": 0.0, "vat": 0.0})
		data.append({
			"vat_category":   f"{box} – {cat}",
			"description_en": cat,
			"description_ar": ar,
			"taxable_amount": b["taxable"],
			"vat_amount":     b["vat"],
		})

	p_taxable = sum(p_buckets[c[0]]["taxable"] for c in _PURCHASE_CATS)
	p_vat     = sum(p_buckets[c[0]]["vat"]     for c in _PURCHASE_CATS)
	data.append({"vat_category": "TOTAL INPUT VAT", "description_en": "Total Input VAT", "description_ar": "إجمالي ضريبة المدخلات", "taxable_amount": p_taxable, "vat_amount": p_vat, "is_total": 1})
	data.append({})

	net_vat = s_vat - p_vat
	data.append({
		"vat_category":   "NET VAT PAYABLE / (REFUNDABLE)",
		"description_en": "Net VAT Payable / (Refundable) to ZATCA",
		"description_ar": "صافي ضريبة القيمة المضافة المستحقة / (القابلة للاسترداد)",
		"taxable_amount": s_taxable - p_taxable,
		"vat_amount":     net_vat,
		"is_net": 1,
	})

	return data


# ─────────────────────────────────────────────
# DETAIL BUILD
# ─────────────────────────────────────────────

def _build_detail(sales_rows, purchase_rows):
	data = []

	data.append({"doctype_label": "── SALES INVOICES ──", "vat_category": "Output VAT / ضريبة المخرجات", "is_group": 1})
	for r in sales_rows:
		data.append({
			"posting_date":   r.get("posting_date"),
			"doctype_label":  r.get("doctype_label"),
			"doctype_name":   r.get("doctype_name"),
			"name":           r.get("name"),
			"party":          r.get("party"),
			"tax_id":         r.get("tax_id"),
			"vat_category":   r.get("vat_category"),
			"taxable_amount": flt(r.get("taxable_amount")),
			"vat_rate":       flt(r.get("vat_rate")),
			"vat_amount":     flt(r.get("vat_amount")),
			"total":          flt(r.get("total")),
			"currency":       r.get("currency"),
		})

	s_taxable = sum(flt(r.get("taxable_amount")) for r in sales_rows)
	s_vat     = sum(flt(r.get("vat_amount"))     for r in sales_rows)
	data.append({"doctype_label": "SUBTOTAL – Sales", "taxable_amount": s_taxable, "vat_amount": s_vat, "is_total": 1})
	data.append({})

	data.append({"doctype_label": "── PURCHASE INVOICES ──", "vat_category": "Input VAT / ضريبة المدخلات", "is_group": 1})
	for r in purchase_rows:
		data.append({
			"posting_date":   r.get("posting_date"),
			"doctype_label":  r.get("doctype_label"),
			"doctype_name":   r.get("doctype_name"),
			"name":           r.get("name"),
			"party":          r.get("party"),
			"tax_id":         r.get("tax_id"),
			"vat_category":   r.get("vat_category"),
			"taxable_amount": flt(r.get("taxable_amount")),
			"vat_rate":       flt(r.get("vat_rate")),
			"vat_amount":     flt(r.get("vat_amount")),
			"total":          flt(r.get("total")),
			"currency":       r.get("currency"),
		})

	p_taxable = sum(flt(r.get("taxable_amount")) for r in purchase_rows)
	p_vat     = sum(flt(r.get("vat_amount"))     for r in purchase_rows)
	data.append({"doctype_label": "SUBTOTAL – Purchases", "taxable_amount": p_taxable, "vat_amount": p_vat, "is_total": 1})
	data.append({})

	net_vat = s_vat - p_vat
	data.append({
		"doctype_label":  "NET VAT PAYABLE / (REFUNDABLE)",
		"taxable_amount": s_taxable - p_taxable,
		"vat_amount":     net_vat,
		"is_net": 1,
	})

	return data


# ─────────────────────────────────────────────
# CHART & SUMMARY CARDS
# ─────────────────────────────────────────────

def get_chart(data, filters):
	mode = (filters or {}).get("report_mode", "Summary")
	if mode != "Summary":
		return None

	labels, output_vat, input_vat = [], [], []
	for r in data:
		cat = r.get("vat_category", "")
		if not cat or "━━" in cat or "TOTAL" in cat or "NET" in cat:
			continue
		labels.append(cat.split("–")[-1].strip()[:28])
		vat = flt(r.get("vat_amount") or 0)
		if any(s in cat for s in ["Box 1", "Box 2", "Box 3", "Box 4", "Box 5"]):
			output_vat.append(vat)
			input_vat.append(0)
		else:
			output_vat.append(0)
			input_vat.append(vat)

	return {
		"data": {
			"labels": labels,
			"datasets": [
				{"name": "Output VAT (Sales)",    "values": output_vat, "chartType": "bar"},
				{"name": "Input VAT (Purchases)", "values": input_vat,  "chartType": "bar"},
			],
		},
		"type": "bar",
		"colors": ["#1C4E80", "#0091D5"],
		"barOptions": {"stacked": False},
	}


def get_report_summary(data, filters):
	s_vat, p_vat = 0.0, 0.0
	for r in data:
		cat = r.get("vat_category", "")
		if cat == "TOTAL OUTPUT VAT":
			s_vat = flt(r.get("vat_amount") or 0)
		elif cat == "TOTAL INPUT VAT":
			p_vat = flt(r.get("vat_amount") or 0)

	net = s_vat - p_vat
	return [
		{"value": s_vat, "label": "Total Output VAT",      "datatype": "Currency", "currency": "SAR", "indicator": "Blue"},
		{"value": p_vat, "label": "Total Input VAT",       "datatype": "Currency", "currency": "SAR", "indicator": "Green"},
		{"value": net,   "label": "Net VAT Payable (SAR)", "datatype": "Currency", "currency": "SAR", "indicator": "Red" if net > 0 else "Green"},
	]


# ═════════════════════════════════════════════════════════════════════
# WHITELISTED PRINT FUNCTIONS  (called from JS via frappe.call)
# ═════════════════════════════════════════════════════════════════════

@frappe.whitelist()
def print_vat_report(filters=None, mode=None):
	"""
	Render the GI VAT Report as a standalone, print-ready HTML page.

	Called from JS:
	    frappe.call({
	        method: "your_app.report.ksa_vat_report.ksa_vat_report.print_vat_report",
	        args: { filters: { ... }, mode: "Summary" },
	        callback: (r) => { open r.message in new window }
	    })

	Returns: { html: "<full page html>", filename: "KSA_VAT_Report_Summary_..." }
	"""
	# ── Parse args ───────────────────────────────────────────────────
	if isinstance(filters, str):
		filters = json.loads(filters)
	filters = filters or {}

	# Allow explicit mode override (for the two separate buttons)
	if mode:
		filters["report_mode"] = mode

	report_mode = filters.get("report_mode", "Summary")
	company_name = filters.get("company") or frappe.defaults.get_user_default("Company")
	from_date    = filters.get("from_date", "")
	to_date      = filters.get("to_date", "")

	# ── Log the print action ─────────────────────────────────────────
	_log_print_action(filters, report_mode)

	# ── Fetch data ───────────────────────────────────────────────────
	data = get_data(filters)

	# ── Fetch company info ───────────────────────────────────────────
	company = _get_company_info(company_name)

	# ── Compute KPI totals ───────────────────────────────────────────
	kpis = _compute_kpis(data, report_mode)

	# ── Render HTML ──────────────────────────────────────────────────
	html = _render_print_html(
		data       = data,
		company    = company,
		filters    = filters,
		report_mode= report_mode,
		from_date  = from_date,
		to_date    = to_date,
		kpis       = kpis,
		user       = frappe.session.user,
		generated  = str(now_datetime()),
	)

	filename = f"KSA_VAT_Report_{report_mode}_{from_date}_{to_date}.html"

	return {"html": html, "filename": filename, "mode": report_mode}


# ─── HELPER: get company doc safely ──────────────────────────────────

def _get_company_info(company_name):
	try:
		c = frappe.get_doc("Company", company_name)
		return {
			"name":              c.company_name,
			"abbr":              c.abbr or "",
			"arabic_name":       getattr(c, "company_name_in_arabic", "") or "",
			"tax_id":            c.tax_id or "",
			"address":           getattr(c, "address_html", "") or "",
			"city":              getattr(c, "city", "") or "",
			"country":           getattr(c, "country", "") or "",
			"phone":             getattr(c, "phone_no", "") or "",
			"email":             getattr(c, "email", "") or "",
			"website":           getattr(c, "website", "") or "",
			"logo":              getattr(c, "custom_logo", "") or "",
		}
	except Exception:
		return {"name": company_name, "abbr": "", "arabic_name": "", "tax_id": "", "address": "", "city": "", "country": "", "phone": "", "email": "", "website": "", "logo": ""}


# ─── HELPER: KPI extraction ───────────────────────────────────────────

def _compute_kpis(data, mode):
	output_taxable = output_vat = input_taxable = input_vat = 0.0

	if mode == "Summary":
		for r in data:
			cat = r.get("vat_category", "")
			if cat == "TOTAL OUTPUT VAT":
				output_taxable = flt(r.get("taxable_amount") or 0)
				output_vat     = flt(r.get("vat_amount")     or 0)
			elif cat == "TOTAL INPUT VAT":
				input_taxable  = flt(r.get("taxable_amount") or 0)
				input_vat      = flt(r.get("vat_amount")     or 0)
	else:
		for r in data:
			lbl = r.get("doctype_label", "")
			if lbl == "SUBTOTAL – Sales":
				output_taxable = flt(r.get("taxable_amount") or 0)
				output_vat     = flt(r.get("vat_amount")     or 0)
			elif lbl == "SUBTOTAL – Purchases":
				input_taxable  = flt(r.get("taxable_amount") or 0)
				input_vat      = flt(r.get("vat_amount")     or 0)

	net_vat     = output_vat - input_vat
	net_taxable = output_taxable - input_taxable
	return {
		"output_taxable": output_taxable,
		"output_vat":     output_vat,
		"input_taxable":  input_taxable,
		"input_vat":      input_vat,
		"net_vat":        net_vat,
		"net_taxable":    net_taxable,
		"is_payable":     net_vat > 0,
	}


# ─── HELPER: format currency ──────────────────────────────────────────

def _fmt(val):
	try:
		return "{:,.2f}".format(flt(val or 0))
	except Exception:
		return "0.00"


# ─── MAIN HTML RENDERER ───────────────────────────────────────────────

def _render_print_html(data, company, filters, report_mode, from_date, to_date, kpis, user, generated):
	"""Build and return the complete standalone print HTML string."""

	# ── Company header block ─────────────────────────────────────────
	logo_html = ""
	if company.get("logo"):
		logo_html = f'<img src="{company["logo"]}" alt="{company["name"]}" style="max-height:64px;max-width:180px;">'
	else:
		logo_html = f'<div class="abbr-logo">{(company.get("abbr") or company["name"][:3]).upper()}</div>'

	arabic_name_html = ""
	if company.get("arabic_name"):
		arabic_name_html = f'<p class="co-arabic">{company["arabic_name"]}</p>'

	contact_lines = []
	if company.get("tax_id"):
		contact_lines.append(f'<p>🔑 VAT Reg No: <strong>{company["tax_id"]}</strong></p>')
	addr = company.get("address") or ""
	if addr:
		import re
		addr_clean = re.sub(r"<[^>]+>", " ", addr).strip()
		if addr_clean:
			contact_lines.append(f"<p>{addr_clean}</p>")
	elif company.get("city") or company.get("country"):
		location = ", ".join(filter(None, [company.get("city"), company.get("country")]))
		contact_lines.append(f"<p>📍 {location}</p>")
	if company.get("phone"):
		contact_lines.append(f'<p>📞 {company["phone"]}</p>')
	if company.get("email"):
		contact_lines.append(f'<p>✉ {company["email"]}</p>')

	contact_html = "\n".join(contact_lines)

	# ── KPI boxes ────────────────────────────────────────────────────
	net_label  = "Net VAT Payable" if kpis["is_payable"] else "Net VAT Refundable"
	net_ar     = "مستحق الدفع" if kpis["is_payable"] else "قابل للاسترداد"
	net_class  = "kpi-payable" if kpis["is_payable"] else "kpi-refund"
	net_sign   = "" if kpis["is_payable"] else "(CR) "

	kpi_html = f"""
	<div class="kpi-strip">
		<div class="kpi-box">
			<div class="kpi-label">Output VAT (Sales)<br><span class="ar">{_fmt(kpis["output_taxable"])} وعاء</span></div>
			<div class="kpi-value">{_fmt(kpis["output_vat"])}</div>
			<div class="kpi-sub">SAR</div>
		</div>
		<div class="kpi-box">
			<div class="kpi-label">Input VAT (Purchases)<br><span class="ar">{_fmt(kpis["input_taxable"])} وعاء</span></div>
			<div class="kpi-value">{_fmt(kpis["input_vat"])}</div>
			<div class="kpi-sub">SAR</div>
		</div>
		<div class="kpi-box {net_class}">
			<div class="kpi-label">{net_label}<br><span class="ar">{net_ar}</span></div>
			<div class="kpi-value">{net_sign}{_fmt(abs(kpis["net_vat"]))}</div>
			<div class="kpi-sub">SAR</div>
		</div>
	</div>"""

	# ── Data table ───────────────────────────────────────────────────
	if report_mode == "Summary":
		table_html = _render_summary_table(data)
	else:
		table_html = _render_detail_table(data)

	# ── Assemble full page ───────────────────────────────────────────
	html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>GI VAT Report – {report_mode} | {company["name"]}</title>
<style>
{_PRINT_CSS}
</style>
</head>
<body>

<!-- ═══ HEADER ═══ -->
<div class="page-header">
	<div class="logo-block">{logo_html}</div>
	<div class="company-info">
		<h1 class="co-name">{company["name"]}</h1>
		{arabic_name_html}
		{contact_html}
	</div>
	<div class="report-title-block">
		<h2 class="rep-title">GI VAT Report</h2>
		<p class="rep-title-ar">تقرير ضريبة القيمة المضافة</p>
		<div class="rep-mode-badge">{report_mode} Mode</div>
		<table class="meta-table">
			<tr><td>Period</td><td><strong>{_fmt_date(from_date)} – {_fmt_date(to_date)}</strong></td></tr>
			<tr><td>Company</td><td>{company["name"]}</td></tr>
			<tr><td>VAT No.</td><td>{company.get("tax_id") or "—"}</td></tr>
			<tr><td>Prepared by</td><td>{user}</td></tr>
			<tr><td>Generated</td><td>{generated}</td></tr>
		</table>
	</div>
</div>

<!-- ═══ KPI STRIP ═══ -->
{kpi_html}

<!-- ═══ DATA TABLE ═══ -->
{table_html}

<!-- ═══ FOOTER ═══ -->
<div class="page-footer">
	<div class="footer-disclaimer">
		This report is generated from <strong>{company["name"]}</strong> ERP system (ERPNext / Frappe Framework).
		All amounts in SAR. Prepared for VAT return filing with ZATCA – هيئة الزكاة والضريبة والجمارك.
		Please verify against your official ZATCA portal submission before filing.
	</div>
	<div class="footer-right">
		<p>Prepared by: <strong>{user}</strong></p>
		<p>Generated: {generated}</p>
		<p class="ar" style="font-size:8pt;color:#aaa;">الزاتكا — هيئة الزكاة والضريبة والجمارك</p>
	</div>
</div>

<script>
// Auto-open print dialog when loaded in new tab via print button
window.onload = function() {{
	if (window.location.hash === '#autoprint') {{
		setTimeout(function() {{ window.print(); }}, 400);
	}}
}};
</script>
</body>
</html>"""

	return html


# ─── SUMMARY TABLE RENDERER ───────────────────────────────────────────

def _render_summary_table(data):
	rows_html = []
	for r in data:
		cat = r.get("vat_category") or ""
		if not cat and not r.get("description_en"):
			rows_html.append('<tr class="spacer-row"><td colspan="5"></td></tr>')
			continue

		taxable = r.get("taxable_amount")
		vat     = r.get("vat_amount")
		tx_cell = f'<td class="num">{_fmt(taxable)}</td>' if taxable is not None else '<td class="num">—</td>'
		vt_cell = f'<td class="num">{_fmt(vat)}</td>'    if vat     is not None else '<td class="num">—</td>'

		if r.get("is_net"):
			rows_html.append(f"""<tr class="row-net">
				<td colspan="3">{r.get("description_en") or cat}
					<span class="ar-inline"> — {r.get("description_ar","")}</span></td>
				{tx_cell}{vt_cell}
			</tr>""")
		elif r.get("is_total"):
			rows_html.append(f"""<tr class="row-total">
				<td colspan="3"><strong>{r.get("description_en") or cat}</strong>
					<span class="ar-inline"> — {r.get("description_ar","")}</span></td>
				{tx_cell}{vt_cell}
			</tr>""")
		elif r.get("is_group"):
			rows_html.append(f"""<tr class="row-group">
				<td>{cat}</td>
				<td colspan="3" class="ar" style="text-align:right;">{r.get("description_ar","")}</td>
				<td></td>
			</tr>""")
		elif cat:
			rows_html.append(f"""<tr>
				<td>{cat}</td>
				<td>{r.get("description_en","")}</td>
				<td class="ar" style="text-align:right;">{r.get("description_ar","")}</td>
				{tx_cell}{vt_cell}
			</tr>""")

	return f"""
<table class="vat-table">
	<thead>
		<tr>
			<th style="width:28%">VAT Category</th>
			<th style="width:26%">Description (EN)</th>
			<th style="width:22%;text-align:right;">الوصف (عربي)</th>
			<th class="num" style="width:12%">Taxable (SAR)</th>
			<th class="num" style="width:12%">VAT (SAR)</th>
		</tr>
	</thead>
	<tbody>{"".join(rows_html)}</tbody>
</table>"""


# ─── DETAIL TABLE RENDERER ────────────────────────────────────────────

def _render_detail_table(data):
	rows_html = []
	for r in data:
		lbl  = r.get("doctype_label") or ""
		name = r.get("name") or ""

		if not lbl and not name and not r.get("is_total") and not r.get("is_net"):
			rows_html.append('<tr class="spacer-row"><td colspan="10"></td></tr>')
			continue

		if r.get("is_net"):
			rows_html.append(f"""<tr class="row-net">
				<td colspan="6">NET VAT PAYABLE / (REFUNDABLE) — صافي ضريبة القيمة المضافة</td>
				<td class="num">{_fmt(r.get("taxable_amount"))}</td>
				<td class="num"></td>
				<td class="num">{_fmt(r.get("vat_amount"))}</td>
				<td></td>
			</tr>""")
		elif r.get("is_total"):
			rows_html.append(f"""<tr class="row-total">
				<td colspan="6"><strong>{lbl}</strong></td>
				<td class="num"><strong>{_fmt(r.get("taxable_amount"))}</strong></td>
				<td class="num"></td>
				<td class="num"><strong>{_fmt(r.get("vat_amount"))}</strong></td>
				<td></td>
			</tr>""")
		elif r.get("is_group"):
			rows_html.append(f"""<tr class="row-group">
				<td colspan="10">{lbl} &nbsp; <span style="font-size:9pt;">{r.get("vat_category","")}</span></td>
			</tr>""")
		elif name:
			rate = r.get("vat_rate")
			rate_cell = f'{int(flt(rate))}%' if rate is not None else "—"
			date_str  = _fmt_date(r.get("posting_date")) if r.get("posting_date") else ""
			rows_html.append(f"""<tr>
				<td>{date_str}</td>
				<td>{lbl}</td>
				<td><strong>{name}</strong></td>
				<td>{r.get("party","")}</td>
				<td style="font-size:8pt;">{r.get("tax_id","")}</td>
				<td style="font-size:8pt;">{r.get("vat_category","")}</td>
				<td class="num">{_fmt(r.get("taxable_amount"))}</td>
				<td class="num">{rate_cell}</td>
				<td class="num">{_fmt(r.get("vat_amount"))}</td>
				<td class="num">{r.get("currency","")}</td>
			</tr>""")

	return f"""
<table class="vat-table">
	<thead>
		<tr>
			<th style="width:8%">Date</th>
			<th style="width:9%">Type</th>
			<th style="width:12%">Document No.</th>
			<th style="width:16%">Party</th>
			<th style="width:11%">VAT No.</th>
			<th style="width:14%">Category</th>
			<th class="num" style="width:10%">Taxable</th>
			<th class="num" style="width:6%">Rate</th>
			<th class="num" style="width:9%">VAT (SAR)</th>
			<th class="num" style="width:5%">CCY</th>
		</tr>
	</thead>
	<tbody>{"".join(rows_html)}</tbody>
</table>"""


# ─── DATE FORMATTER ───────────────────────────────────────────────────

def _fmt_date(d):
	try:
		return formatdate(str(d), "dd-MM-yyyy") if d else ""
	except Exception:
		return str(d) if d else ""


# ─── PRINT CSS (embedded) ─────────────────────────────────────────────

_PRINT_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:"Segoe UI",Arial,sans-serif;font-size:10pt;color:#1A252F;background:#fff;padding:18px 24px}
.ar{font-family:"Segoe UI",Tahoma,Arial,sans-serif;direction:rtl}
.ar-inline{font-family:"Segoe UI",Tahoma,Arial,sans-serif;direction:rtl;font-size:9pt;color:#555}

/* ── HEADER ── */
.page-header{display:flex;align-items:flex-start;gap:18px;border-bottom:3px solid #1C4E80;padding-bottom:14px;margin-bottom:16px}
.logo-block{min-width:100px;text-align:center}
.abbr-logo{font-size:24pt;font-weight:900;color:#1C4E80;letter-spacing:-2px;line-height:1}
.company-info{flex:1}
.co-name{font-size:14pt;font-weight:800;color:#1C4E80;margin-bottom:3px}
.co-arabic{font-size:12pt;font-weight:700;color:#1C4E80;direction:rtl;margin-bottom:4px}
.company-info p{font-size:8.5pt;color:#555;margin-top:2px}
.report-title-block{min-width:220px;text-align:right}
.rep-title{font-size:13pt;font-weight:800;color:#1C4E80}
.rep-title-ar{font-size:11pt;font-weight:700;color:#1C4E80;direction:rtl;margin-bottom:6px}
.rep-mode-badge{display:inline-block;background:#1C4E80;color:#fff;font-size:8pt;padding:2px 10px;border-radius:12px;margin-bottom:6px;font-weight:600;letter-spacing:.5px}
.meta-table{font-size:8.5pt;border-collapse:collapse;width:100%}
.meta-table td{padding:2px 4px;color:#444}
.meta-table td:first-child{color:#777;white-space:nowrap;padding-right:8px}

/* ── KPI STRIP ── */
.kpi-strip{display:flex;gap:14px;margin:16px 0}
.kpi-box{flex:1;border:2px solid #2980B9;border-radius:6px;padding:10px 14px;text-align:center;background:#F8FBFF}
.kpi-label{font-size:8pt;color:#555;text-transform:uppercase;letter-spacing:.4px;margin-bottom:4px}
.kpi-value{font-size:15pt;font-weight:800;color:#1C4E80}
.kpi-sub{font-size:8pt;color:#999;margin-top:2px}
.kpi-payable .kpi-value{color:#C0392B}
.kpi-payable{border-color:#C0392B;background:#FDF4F4}
.kpi-refund .kpi-value{color:#1E8449}
.kpi-refund{border-color:#1E8449;background:#F4FDF6}
.kpi-box .ar{font-size:8pt;color:#888}

/* ── TABLE ── */
.vat-table{width:100%;border-collapse:collapse;font-size:9pt;margin-bottom:14px}
.vat-table th{background:#1C4E80;color:#fff;padding:7px 8px;text-align:left;font-size:8.5pt;font-weight:600}
.vat-table th.num,.vat-table td.num{text-align:right;font-family:"Courier New",monospace}
.vat-table td{padding:5px 8px;border-bottom:1px solid #E4EDF5;vertical-align:middle}
.vat-table tbody tr:nth-child(even) td{background:#F8FBFD}
.vat-table tbody tr:hover td{background:#EBF5FB}
tr.row-group td{background:#D6EAF8!important;font-weight:700;color:#1C4E80;font-size:9.5pt;padding:5px 8px}
tr.row-total td{background:#AED6F1!important;font-weight:700;border-top:2px solid #1C4E80;border-bottom:2px solid #1C4E80}
tr.row-net td{background:#1C4E80!important;color:#fff!important;font-weight:700;font-size:9.5pt}
tr.row-net td.num{color:#FFD700!important}
tr.spacer-row td{padding:3px 0;border:none;background:transparent!important}

/* ── FOOTER ── */
.page-footer{margin-top:20px;border-top:2px solid #1C4E80;padding-top:10px;display:flex;justify-content:space-between;gap:20px;font-size:8pt;color:#777}
.footer-disclaimer{max-width:65%;line-height:1.5}
.footer-right{text-align:right;min-width:200px}
.footer-right p{margin-top:3px}

/* ── PRINT MEDIA ── */
@media print{
	body{padding:10mm 12mm;font-size:9pt}
	.kpi-strip{break-inside:avoid}
	.page-header{break-after:avoid}
	tr.row-group{break-after:avoid}
	.vat-table tr{break-inside:avoid}
	.page-footer{break-before:avoid}
}
"""


# ─────────────────────────────────────────────
# LOGGER
# ─────────────────────────────────────────────

def _log_report_run(filters):
	"""Log every execute() call."""
	try:
		user    = frappe.session.user
		company = (filters or {}).get("company") or frappe.defaults.get_user_default("Company")
		mode    = (filters or {}).get("report_mode", "Summary")
		f_date  = (filters or {}).get("from_date", "")
		t_date  = (filters or {}).get("to_date", "")

		msg = (
			f"[GI VAT Report | RUN] User={user} | Company={company} | "
			f"Mode={mode} | Period={f_date}→{t_date} | At={now_datetime()}"
		)
		frappe.logger("ksa_vat_report").info(msg)
		_write_activity_log(msg)

	except Exception as e:
		frappe.log_error(f"GI VAT Report logger error: {e}", "GI VAT Report")


def _log_print_action(filters, mode):
	"""Log every print_vat_report() call."""
	try:
		user    = frappe.session.user
		company = (filters or {}).get("company") or frappe.defaults.get_user_default("Company")
		f_date  = (filters or {}).get("from_date", "")
		t_date  = (filters or {}).get("to_date", "")

		msg = (
			f"[GI VAT Report | PRINT] User={user} | Company={company} | "
			f"Mode={mode} | Period={f_date}→{t_date} | At={now_datetime()}"
		)
		frappe.logger("ksa_vat_report").info(msg)
		_write_activity_log(msg, subject=f"GI VAT Report Print – {mode}")

	except Exception as e:
		frappe.log_error(f"GI VAT Report print logger error: {e}", "GI VAT Report")


def _write_activity_log(msg, subject="GI VAT Report Run"):
	"""Write to Frappe Activity Log if the doctype exists."""
	try:
		frappe.get_doc({
			"doctype":            "Activity Log",
			"subject":            subject,
			"content":            msg,
			"reference_doctype":  "Report",
			"reference_name":     "GI VAT Report",
			"user":               frappe.session.user,
		}).insert(ignore_permissions=True)
	except Exception:
		pass  # Activity Log not available in all ERPNext versions
