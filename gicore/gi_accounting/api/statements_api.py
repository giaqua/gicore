# Copyright (c) 2026, GI Aqua Tech and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from werkzeug.wrappers import Response
from frappe.utils import formatdate, fmt_money, now_datetime, cint
from frappe.utils.pdf import get_pdf
from gicore.gi_accounting.api.statement_engine import get_statement_data

TEMPLATE = "gicore/gi_accounting/templates/statement_of_account.html"


@frappe.whitelist()
def statement_print(party_type, party, company, from_date, to_date, as_pdf=0):
	"""Render a professional IFRS-style Statement of Account.

	Opens as printable HTML in a new tab, or downloads as PDF when as_pdf=1.
	"""
	if party_type not in ("Customer", "Supplier"):
		frappe.throw(_("Invalid party type"))

	if not frappe.has_permission(party_type, "read", party):
		frappe.throw(_("Not permitted"), frappe.PermissionError)

	data = get_statement_data(party_type, party, company, from_date, to_date)

	html = frappe.render_template(
		TEMPLATE,
		{
			"d": data,
			"generated_on": now_datetime().strftime("%d-%m-%Y %H:%M"),
			"fmt": lambda v: fmt_money(v, currency=data.currency),
			"fdate": lambda v: formatdate(v, "dd-MM-yyyy"),
		},
	)

	if cint(as_pdf):
		frappe.local.response.filename = "{0} Statement - {1}.pdf".format(
			party_type, data.party_name
		)
		frappe.local.response.filecontent = get_pdf(
			html,
			{
				"page-size": "A4",
				"margin-top": "12mm",
				"margin-bottom": "14mm",
				"margin-left": "10mm",
				"margin-right": "10mm",
			},
		)
		frappe.local.response.type = "pdf"
		return

	return Response(html, content_type="text/html; charset=utf-8")
