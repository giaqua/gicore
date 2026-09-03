# Copyright (c) 2026, GI Aqua Tech and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class HMBusinessCard(Document):
	pass

# your_app/your_app/utils/print_card.py
import base64
from io import BytesIO

import frappe
import qrcode


def _generate_qr_base64(data: str) -> str:
    qr = qrcode.QRCode(box_size=6, border=1)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0E3B3B", back_color="#F4F1E8")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _build_card_html(doc) -> str:
    clean_phone = (doc.phone or "").replace("+", "").replace(" ", "").replace("-", "")

    vcard = (
        "BEGIN:VCARD\nVERSION:3.0\n"
        f"FN:{doc.full_name}\n"
        f"ORG:{doc.company or ''}\n"
        f"TEL:{doc.phone or ''}\n"
        f"EMAIL:{doc.email or ''}\n"
        "END:VCARD"
    )
    whatsapp_url = f"https://wa.me/{clean_phone}"

    contact_qr = _generate_qr_base64(vcard)
    whatsapp_qr = _generate_qr_base64(whatsapp_url)

    designation_html = f'<p class="role">{doc.designation}</p>' if doc.designation else ""

    return f"""
    <html>
    <head>
    <style>
        @media print {{
            @page {{ size: 85mm 55mm; margin: 0; }}
        }}
        * {{ box-sizing: border-box; }}
        html, body {{
            margin: 0;
            padding: 0;
            font-family: 'Helvetica', 'Arial', sans-serif;
        }}
        .card {{
            width: 85mm;
            height: 55mm;
            background: linear-gradient(165deg, #103F3F 0%, #0B2E2E 100%);
            color: #F4F1E8;
            padding: 14px 16px;
            overflow: hidden;
        }}
        .mark {{ font-size: 8px; letter-spacing: 0.02em; color: #4FC3B0; margin: 0 0 6px; }}
        h1 {{ font-size: 16px; margin: 0 0 1px; color: #F4F1E8; line-height: 1.1; }}
        .role {{ font-size: 8px; color: rgba(244,241,232,0.55); margin: 0 0 6px; }}
        .divider {{ height: 1px; background: rgba(217,210,188,0.18); margin: 0 0 8px; }}
        .field {{ font-size: 8px; margin-bottom: 3px; }}
        .field span {{ color: #4FC3B0; display: inline-block; width: 34px; }}
        .actions {{ margin-top: 8px; display: flex; gap: 10px; }}
        .actions div {{ text-align: center; }}
        .actions img {{ background: #F4F1E8; padding: 3px; border-radius: 4px; width: 46px; height: 46px; }}
        .actions p {{ font-size: 6px; color: rgba(244,241,232,0.6); margin: 2px 0 0; }}
    </style>
    </head>
    <body>
        <div class="card">
            <div class="mark">{doc.company or ''}</div>
            <h1>{doc.full_name}</h1>
            {designation_html}
            <div class="divider"></div>
            <div class="field"><span>Phone</span>{doc.phone or ''}</div>
            <div class="field"><span>Email</span>{doc.email or ''}</div>
            <div class="actions">
                <div>
                    <img src="data:image/png;base64,{contact_qr}">
                    <p>Scan to save contact</p>
                </div>
                <div>
                    <img src="data:image/png;base64,{whatsapp_qr}">
                    <p>Scan to chat</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@frappe.whitelist()
def get_business_card_html(docname):
    doc = frappe.get_doc("HM Business Card", docname)
    doc.check_permission("read")
    return _build_card_html(doc)