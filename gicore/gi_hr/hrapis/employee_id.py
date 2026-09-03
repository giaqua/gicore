# /home/frappe/frappe-bench-15/apps/gicore/gicore/gi_hr/hrapis/employee_id.py

import frappe
from frappe.utils.pdf import get_pdf
from io import BytesIO


def _get_photo_url(doc):
	if doc.image:
		return frappe.utils.get_url(doc.image)
	return frappe.utils.get_url("/assets/frappe/images/ui/avatar.png")


def _get_barcode_svg(value):
	"""Generate an inline SVG barcode. Requires python-barcode (pip install python-barcode)."""
	try:
		import barcode
		from barcode.writer import SVGWriter

		buffer = BytesIO()
		code128 = barcode.get("code128", value, writer=SVGWriter())
		code128.write(buffer, options={"write_text": False, "module_height": 8, "quiet_zone": 1})
		return buffer.getvalue().decode("utf-8")
	except Exception:
		return ""


def _build_id_card_html(doc):
	"""Builds front/back ID card HTML. All classes prefixed with 'idc-' to avoid
	colliding with Frappe/Bootstrap's own .card, .name, .info, .back, .corner etc."""

	image = _get_photo_url(doc)
	barcode_svg = _get_barcode_svg(doc.name)

	html = """
	<div class="idc-wrapper">
	<style>
	  .idc-wrapper {{ all: initial; }}
	  .idc-wrapper * {{ box-sizing: border-box; font-family: Arial, sans-serif; }}

	  @page {{ size: 85.6mm 54mm; margin: 0; }}

	  .idc-card {{
	    width: 85.6mm; height: 54mm;
	    position: relative;
	    page-break-after: always;
	    overflow: hidden;
	    background: #ffffff;
	    margin: 0 0 4mm 0;
	    display: block;
	    border: 1px solid #ddd; /* remove this line if you don't want a visible edge on screen */
	  }}
	  .idc-card:last-child {{ page-break-after: auto; margin-bottom: 0; }}

	  .idc-stripe {{
	    position: absolute; top: 0; left: 0; bottom: 0; width: 12mm;
	    background: #0d3f8c;
	  }}
	  .idc-stripe-cut {{
	    position: absolute; top: 0; left: 12mm; width: 0; height: 0;
	    border-top: 54mm solid #0d3f8c;
	    border-right: 6mm solid transparent;
	  }}
	  .idc-corner {{
	    position: absolute; bottom: 0; right: 0; width: 0; height: 0;
	    border-bottom: 16mm solid #1a5cb8;
	    border-left: 22mm solid transparent;
	  }}
	  .idc-blob {{
	    position: absolute; top: -8mm; right: -8mm; width: 22mm; height: 22mm;
	    background: #eaf1fb;
	    border-radius: 50%;
	  }}
	  .idc-logo {{ position: absolute; top: 3mm; left: 16mm; font-size: 9px; font-weight: bold; color: #0d3f8c; }}
	  .idc-logo span {{ display:block; font-weight: normal; font-size: 8px; color: #0d3f8c; }}

	  .idc-photo {{
	    position: absolute; top: 9mm; left: 30mm; width: 22mm; height: 22mm;
	    border-radius: 50%; border: 1px solid #eeeeee;
	    background-image: url('{image}');
	    background-size: cover;
	    background-position: center;
	  }}

	  .idc-emp-name {{ position: absolute; top: 33mm; left: 14mm; width: 58mm; text-align:center; font-size: 13px; font-weight: bold; color: #17253d; }}
	  .idc-designation {{
	    position: absolute; top: 38mm; left: 26mm; font-size: 7.5px; font-weight: bold;
	    background: #1a5cb8; color: #ffffff; padding: 1.2mm 4mm; border-radius: 1mm; text-align:center;
	  }}
	  .idc-info {{ position: absolute; top: 43mm; left: 14mm; font-size: 6.8px; line-height: 1.7; color: #1c1c1c; }}
	  .idc-info b {{ display:inline-block; width: 12mm; }}

	  .idc-barcode {{ position: absolute; bottom: 1mm; left: 14mm; width: 58mm; text-align:center; }}
	  .idc-barcode svg {{ width: 100%; height: 6mm; }}

	  .idc-back-title {{ position: absolute; top: 5mm; left: 5mm; font-size: 9px; font-weight: bold; color: #0d3f8c; }}
	  .idc-back-content {{ position: absolute; top: 12mm; left: 5mm; right: 5mm; font-size: 7px; line-height: 1.8; color: #333333; }}
	  .idc-back-footer {{ position: absolute; bottom: 3mm; left: 5mm; right: 5mm; font-size: 6px; text-align:center; color: #888888; }}
	</style>

	<!-- FRONT -->
	<div class="idc-card idc-front">
	  <div class="idc-blob"></div>
	  <div class="idc-stripe"></div>
	  <div class="idc-stripe-cut"></div>
	  <div class="idc-corner"></div>

	  <div class="idc-logo">{company}<span>Employee ID</span></div>

	  <div class="idc-photo"></div>

	  <div class="idc-emp-name">{employee_name}</div>
	  <div class="idc-designation">{designation}</div>

	  <div class="idc-info">
	    <b>ID No</b>: {employee_id}<br>
	    <b>Email</b>: {email}<br>
	    <b>Dept</b>: {department}<br>
	    <b>Phone</b>: {phone}
	  </div>

	  <div class="idc-barcode">{barcode_svg}</div>
	</div>

	<!-- BACK -->
	<div class="idc-card idc-back">
	  <div class="idc-stripe"></div>
	  <div class="idc-blob"></div>
	  <div class="idc-back-title">{company}</div>
	  <div class="idc-back-content">
	    <b>Emergency Contact:</b> {emergency_phone}<br>
	    <b>Blood Group:</b> {blood_group}<br>
	    <b>Date of Joining:</b> {date_of_joining}<br>
	    <b>Address:</b> {address}
	  </div>
	  <div class="idc-back-footer">If found, please return to HR Department — {company}</div>
	</div>
	</div>
	""".format(
		company=frappe.utils.escape_html(doc.company or ""),
		image=image,
		employee_name=frappe.utils.escape_html(doc.employee_name or ""),
		designation=frappe.utils.escape_html(doc.designation or ""),
		employee_id=frappe.utils.escape_html(doc.name or ""),
		email=frappe.utils.escape_html(doc.company_email or doc.personal_email or ""),
		department=frappe.utils.escape_html(doc.department or ""),
		phone=frappe.utils.escape_html(doc.cell_number or doc.phone or ""),
		barcode_svg=barcode_svg,
		emergency_phone=frappe.utils.escape_html(doc.emergency_phone_number or ""),
		blood_group=frappe.utils.escape_html(doc.blood_group or ""),
		date_of_joining=frappe.utils.format_date(doc.date_of_joining) if doc.date_of_joining else "",
		address=frappe.utils.escape_html(doc.current_address or ""),
	)

	return html

@frappe.whitelist()
def get_id_card_html(employee):
	"""Returns rendered HTML for the review/preview step (called from the Client Script dialog)."""
	if not frappe.has_permission("Employee", "read", employee):
		frappe.throw(frappe._("Not permitted"))

	doc = frappe.get_doc("Employee", employee)
	return _build_id_card_html(doc)


@frappe.whitelist()
def download_id_card_pdf(employee):
	"""Generates and streams the final 2-page (front/back) PDF, after the user confirms the preview."""
	if not frappe.has_permission("Employee", "read", employee):
		frappe.throw(frappe._("Not permitted"))

	doc = frappe.get_doc("Employee", employee)
	html = _build_id_card_html(doc)
	pdf = get_pdf(html)

	frappe.local.response.filename = f"{doc.name}-id-card.pdf"
	frappe.local.response.filecontent = pdf
	frappe.local.response.type = "download"