# /home/frappe/frappe-bench-15/apps/gicore/gicore/gi_hr/hrapis/employee_id.py

import frappe
from frappe.utils.pdf import get_pdf
from io import BytesIO


def _get_photo_url(doc):
	if doc.image:
		return frappe.utils.get_url(doc.image)
	return frappe.utils.get_url("/assets/frappe/images/ui/avatar.png")


def _get_barcode_svg(value):
	"""Generate an inline SVG barcode, with explicit width/height baked in
	(prevents wkhtmltopdf from letting an oversized SVG spill onto the next page)."""
	try:
		import barcode
		from barcode.writer import SVGWriter

		buffer = BytesIO()
		code128 = barcode.get("code128", value, writer=SVGWriter())
		code128.write(buffer, options={
			"write_text": False,
			"module_height": 8,
			"module_width": 0.25,
			"quiet_zone": 1,
		})
		svg = buffer.getvalue().decode("utf-8")

		# force explicit width/height on the <svg> tag itself so it can't overflow
		svg = svg.replace("<svg ", '<svg width="44mm" height="8mm" preserveAspectRatio="none" ', 1)
		return svg
	except Exception:
		return ""


def _build_id_card_html(doc):
	"""Vertical (portrait) ID card — 54mm x 85.6mm, front + back.
	All classes prefixed 'idc-' to avoid colliding with Frappe/Bootstrap CSS.
	Uses only wkhtmltopdf-safe CSS (no clip-path, no object-fit, no radial-gradient)."""

	image = _get_photo_url(doc)
	barcode_svg = _get_barcode_svg(doc.name)

	html = """
	<div class="idc-wrapper">
	<style>
	  .idc-wrapper {{ all: initial; }}
	  .idc-wrapper * {{ box-sizing: border-box; font-family: Arial, sans-serif; }}

	  @page {{ size: 54mm 85.6mm; margin: 0; }}

	  .idc-card {{
	    width: 54mm; height: 85.6mm;
	    position: relative;
	    page-break-after: always;
	    overflow: hidden;
	    background: #ffffff;
	    margin: 0 auto 6mm auto;
	    display: block;
	    border: 1px solid #ddd;
	  }}
	  .idc-card:last-child {{ page-break-after: auto; margin-bottom: 0; }}

	  /* top diagonal ribbon, built with borders instead of clip-path */
	  .idc-ribbon-base {{
	    position: absolute; top: 0; left: 0; width: 54mm; height: 16mm;
	    background: #0d3f8c;
	  }}
	  .idc-ribbon-cut {{
	    position: absolute; top: 16mm; left: 0; width: 0; height: 0;
	    border-left: 54mm solid #0d3f8c;
	    border-bottom: 6mm solid transparent;
	  }}

	  /* soft circle accent, bottom-left on front */
	  .idc-blob {{
	    position: absolute; bottom: -10mm; left: -10mm; width: 24mm; height: 24mm;
	    background: #eaf1fb;
	    border-radius: 50%;
	  }}

	  /* small corner triangle bottom-right */
	  .idc-corner {{
	    position: absolute; bottom: 0; right: 0; width: 0; height: 0;
	    border-bottom: 14mm solid #1a5cb8;
	    border-left: 14mm solid transparent;
	  }}

	  .idc-logo {{
	    position: absolute; top: 4mm; left: 0; width: 54mm; text-align: center;
	    font-size: 10px; font-weight: bold; color: #ffffff; letter-spacing: 0.3px;
	  }}
	  .idc-logo span {{ display:block; font-weight: normal; font-size: 7.5px; color: #dce8fb; margin-top: 0.5mm; }}

	  .idc-photo {{
	    position: absolute; top: 20mm; left: 15mm; width: 24mm; height: 24mm;
	    border-radius: 50%; border: 2px solid #ffffff;
	    background-image: url('{image}');
	    background-size: cover;
	    background-position: center;
	    box-shadow: 0 0 0 1px #d8d8d8;
	  }}

	  .idc-emp-name {{
	    position: absolute; top: 47mm; left: 2mm; width: 50mm; text-align:center;
	    font-size: 12.5px; font-weight: bold; color: #17253d;
	  }}
	  .idc-designation {{
	    position: absolute; top: 53mm; left: 12mm; width: 30mm; text-align:center;
	    font-size: 7px; font-weight: bold;
	    background: #1a5cb8; color: #ffffff; padding: 1.3mm 0; border-radius: 1mm;
	  }}

	  .idc-divider {{
	    position: absolute; top: 60mm; left: 5mm; width: 44mm; height: 0;
	    border-top: 0.4mm solid #e2e2e2;
	  }}

	  .idc-info {{ position: absolute; top: 63mm; left: 5mm; width: 44mm; font-size: 6.8px; line-height: 2.1; color: #2b2b2b; }}
	  .idc-info b {{ display:inline-block; width: 13mm; color: #0d3f8c; }}

	  .idc-barcode {{
        position: absolute; bottom: 3mm; left: 5mm; width: 44mm; height: 8mm;
        text-align:center; overflow: hidden;
        }}
        .idc-barcode svg {{ width: 44mm !important; height: 8mm !important; display: block; margin: 0 auto; }}

	  /* back side */
	  .idc-back-header {{
	    position: absolute; top: 0; left: 0; width: 54mm; height: 10mm;
	    background: #0d3f8c; text-align:center;
	  }}
	  .idc-back-header span {{ color: #ffffff; font-size: 9px; font-weight: bold; line-height: 10mm; }}

	  .idc-back-content {{ position: absolute; top: 15mm; left: 5mm; right: 5mm; font-size: 7px; line-height: 2; color: #333333; }}
	  .idc-back-content b {{ color: #0d3f8c; }}

	  .idc-back-footer {{
	    position: absolute; bottom: 4mm; left: 4mm; right: 4mm; font-size: 6px;
	    text-align:center; color: #999999; border-top: 0.3mm solid #eee; padding-top: 2mm;
	  }}
	</style>

	<!-- FRONT -->
	<div class="idc-card idc-front">
	  <div class="idc-blob"></div>
	  <div class="idc-ribbon-base"></div>
	  <div class="idc-ribbon-cut"></div>
	  <div class="idc-corner"></div>

	  <div class="idc-logo">{company}<span>EMPLOYEE ID CARD</span></div>

	  <div class="idc-photo"></div>

	  <div class="idc-emp-name">{employee_name}</div>
	  <div class="idc-designation">{designation}</div>

	  <div class="idc-divider"></div>

	  <div class="idc-info">
	    <b>ID No</b>{employee_id}<br>
	    <b>Email</b>{email}<br>
	    <b>Dept</b>{department}<br>
	    <b>Phone</b>{phone}
	  </div>

	  
	</div>

	<!-- BACK -->
	<div class="idc-card idc-back">
	  <div class="idc-back-header"><span>{company}</span></div>
	  <div class="idc-back-content">
	    <b>Emergency Contact:</b><br>{emergency_phone}<br><br>
	    <b>Blood Group:</b> {blood_group}<br><br>
	    <b>Date of Joining:</b><br>{date_of_joining}<br><br>
	    <b>Address:</b><br>{address}
	  </div>
	  <div class="idc-back-footer">If found, please return to HR Department — {company}</div>
	  <div class="idc-barcode">{barcode_svg}</div>
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