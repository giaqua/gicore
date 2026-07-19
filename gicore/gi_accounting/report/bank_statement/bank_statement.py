# Copyright (c) 2026
import frappe
from frappe import _
from frappe.utils import flt, fmt_money, formatdate, getdate, cstr


def execute(filters=None):
    filters = frappe._dict(filters or {})

    validate_filters(filters)

    columns = get_columns()
    data = get_data(filters)

    return columns, data


def validate_filters(filters):
    if not filters.get("account"):
        frappe.throw(_("Please select a Bank Account"))
    if not filters.get("company"):
        frappe.throw(_("Please select a Company"))
    if not filters.get("from_date") or not filters.get("to_date"):
        frappe.throw(_("Please select From Date and To Date"))

    # enforce that only Bank/Cash type accounts can be used here
    account_type = frappe.db.get_value("Account", filters.account, "account_type")
    if account_type not in ("Bank", "Cash"):
        frappe.throw(_("Selected account {0} is not a Bank/Cash account").format(
            frappe.bold(filters.account)
        ))


def get_columns():
    return [
        {"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 90},
        {"label": _("Voucher Type"), "fieldname": "voucher_type", "fieldtype": "Data", "width": 120},
        {"label": _("Voucher No"), "fieldname": "voucher_no", "fieldtype": "Dynamic Link",
         "options": "voucher_type", "width": 160},
        {"label": _("Reference No"), "fieldname": "cheque_no", "fieldtype": "Data", "width": 110},
        {"label": _("Reference Date"), "fieldname": "reference_date", "fieldtype": "Date", "width": 100},
        {"label": _("Party Type"), "fieldname": "party_type", "fieldtype": "Data", "width": 100},
        {"label": _("Party"), "fieldname": "party", "fieldtype": "Dynamic Link",
         "options": "party_type", "width": 140},
        {"label": _("Against Account"), "fieldname": "against", "fieldtype": "Data", "width": 160},
        {"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 120},
        {"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 120},
        {"label": _("Balance"), "fieldname": "balance", "fieldtype": "Currency", "width": 130},
        {"label": _("Remarks"), "fieldname": "remarks", "fieldtype": "Data", "width": 200},
    ]


def get_data(filters):
    if filters.get("remarks"):
        filters["remarks"] = "%{0}%".format(filters.get("remarks"))
    if filters.get("reference_no"):
        filters["reference_no"] = "%{0}%".format(filters.get("reference_no"))

    inner_conditions = get_inner_conditions(filters)
    outer_conditions = get_outer_conditions(filters)

    opening_balance = get_opening_balance(filters)

    gl_entries = frappe.db.sql(
        """
        select * from (
            select
                gl.posting_date,
                gl.voucher_type,
                gl.voucher_no,
                gl.party_type,
                gl.party,
                gl.against,
                gl.debit,
                gl.credit,
                gl.remarks,
                case gl.voucher_type
                    when 'Payment Entry' then pe.reference_no
                    when 'Journal Entry' then je.cheque_no
                    else null
                end as cheque_no,
                case gl.voucher_type
                    when 'Payment Entry' then pe.reference_date
                    when 'Journal Entry' then je.cheque_date
                    else null
                end as reference_date
            from `tabGL Entry` gl
            left join `tabPayment Entry` pe
                on gl.voucher_type = 'Payment Entry' and gl.voucher_no = pe.name
            left join `tabJournal Entry` je
                on gl.voucher_type = 'Journal Entry' and gl.voucher_no = je.name
            where
                gl.account = %(account)s
                and gl.company = %(company)s
                and gl.is_cancelled = 0
                and gl.posting_date between %(from_date)s and %(to_date)s
                {inner_conditions}
        ) result
        where 1=1
        {outer_conditions}
        order by result.posting_date asc
        """.format(inner_conditions=inner_conditions, outer_conditions=outer_conditions),
        filters,
        as_dict=1,
    )

    data = []

    # opening balance row
    data.append({
        "posting_date": filters.from_date,
        "voucher_type": "",
        "voucher_no": "",
        "party": "",
        "against": "Opening Balance",
        "debit": 0,
        "credit": 0,
        "balance": opening_balance,
        "bold": 1
    })

    running_balance = opening_balance

    total_debit = 0
    total_credit = 0

    for row in gl_entries:
        running_balance += flt(row.debit) - flt(row.credit)
        row["balance"] = running_balance
        total_debit += flt(row.debit)
        total_credit += flt(row.credit)
        data.append(row)

    # closing balance row
    data.append({
        "posting_date": filters.to_date,
        "against": "Closing Balance",
        "debit": total_debit,
        "credit": total_credit,
        "balance": running_balance,
        "bold": 1
    })

    return data


def get_inner_conditions(filters):
    """Conditions on raw GL Entry / joined columns (evaluated inside the subquery)"""
    conditions = ""

    if filters.get("party_type"):
        conditions += " and gl.party_type = %(party_type)s"
    if filters.get("party"):
        conditions += " and gl.party = %(party)s"
    if filters.get("voucher_type"):
        conditions += " and gl.voucher_type = %(voucher_type)s"
    if filters.get("voucher_no"):
        conditions += " and gl.voucher_no = %(voucher_no)s"
    if filters.get("remarks"):
        conditions += " and gl.remarks like %(remarks)s"

    return conditions


def get_outer_conditions(filters):
    """Conditions on computed columns (evaluated outside the subquery, e.g. cheque_no)"""
    conditions = ""

    if filters.get("reference_no"):
        conditions += " and result.cheque_no like %(reference_no)s"

    return conditions


def get_opening_balance(filters):
    result = frappe.db.sql(
        """
        select sum(debit) - sum(credit) as balance
        from `tabGL Entry`
        where
            account = %(account)s
            and company = %(company)s
            and is_cancelled = 0
            and posting_date < %(from_date)s
        """,
        filters,
    )
    return flt(result[0][0]) if result else 0.0


@frappe.whitelist()
def download_bank_statement_pdf(**filters):
    """Renders the bank statement as a designed PDF and streams it back for download."""
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    data = get_data(filters)

    account_doc = frappe.get_cached_doc("Account", filters.account)
    company_doc = frappe.get_cached_doc("Company", filters.company)
    currency = company_doc.default_currency

    rows = [r for r in data if r.get("voucher_no") or r.get("against") in ("Opening Balance", "Closing Balance")]

    html = frappe.render_template(
        get_print_template(),
        {
            "company": company_doc,
            "account": account_doc,
            "filters": filters,
            "rows": rows,
            "currency": currency,
            "fmt_money": fmt_money,
            "formatdate": formatdate,
            "from_date": formatdate(filters.from_date),
            "to_date": formatdate(filters.to_date),
            "generated_on": frappe.utils.now_datetime().strftime("%d-%m-%Y %H:%M"),
        },
    )

    pdf_content = frappe.utils.pdf.get_pdf(html, {"orientation": "Landscape"})

    frappe.local.response.filename = "Bank Statement - {0} - {1} to {2}.pdf".format(
        cstr(account_doc.account_name), formatdate(filters.from_date), formatdate(filters.to_date)
    )
    frappe.local.response.filecontent = pdf_content
    frappe.local.response.type = "download"


def get_print_template():
    return """
    <html>
    <head>
    <style>
        @page { size: A4 landscape; margin: 14mm; }
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            color: #1f2937;
            font-size: 10px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            border-bottom: 3px solid #0b3d91;
            padding-bottom: 10px;
            margin-bottom: 14px;
        }
        .company-name {
            font-size: 18px;
            font-weight: 700;
            color: #0b3d91;
            margin: 0;
        }
        .statement-title {
            font-size: 13px;
            color: #6b7280;
            margin-top: 2px;
            letter-spacing: 0.5px;
            text-transform: uppercase;
        }
        .meta-box {
            text-align: right;
            font-size: 10px;
            color: #374151;
            line-height: 1.6;
        }
        .meta-box b { color: #0b3d91; }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 6px;
        }
        thead th {
            background: #0b3d91;
            color: #ffffff;
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 0.3px;
            padding: 7px 6px;
            text-align: left;
        }
        tbody td {
            padding: 5px 6px;
            border-bottom: 1px solid #e5e7eb;
            font-size: 9.5px;
        }
        tbody tr:nth-child(even) { background: #f8fafc; }
        .text-right { text-align: right; }
        .balance-row td {
            background: #eef2ff !important;
            font-weight: 700;
            border-top: 2px solid #0b3d91;
            border-bottom: 2px solid #0b3d91;
        }
        .footer {
            margin-top: 16px;
            font-size: 8.5px;
            color: #9ca3af;
            border-top: 1px solid #e5e7eb;
            padding-top: 6px;
        }
    </style>
    </head>
    <body>
        <div class="header">
            <div>
                <p class="company-name">{{ company.company_name }}</p>
                <p class="statement-title">Bank Statement</p>
            </div>
            <div class="meta-box">
                <div><b>Account:</b> {{ account.account_name }}</div>
                <div><b>Period:</b> {{ from_date }} to {{ to_date }}</div>
                <div><b>Currency:</b> {{ currency }}</div>
            </div>
        </div>

        <table>
            <thead>
                <tr>
                    <th>Date</th>
                    <th>Voucher Type</th>
                    <th>Voucher No</th>
                    <th>Reference No</th>
                    <th>Party</th>
                    <th>Against</th>
                    <th class="text-right">Debit</th>
                    <th class="text-right">Credit</th>
                    <th class="text-right">Balance</th>
                    <th>Remarks</th>
                </tr>
            </thead>
            <tbody>
                {% for row in rows %}
                <tr class="{{ 'balance-row' if row.bold else '' }}">
                    <td>{{ formatdate(row.posting_date) if row.posting_date else '' }}</td>
                    <td>{{ row.voucher_type or '' }}</td>
                    <td>{{ row.voucher_no or '' }}</td>
                    <td>{{ row.cheque_no or '' }}</td>
                    <td>{{ row.party or '' }}</td>
                    <td>{{ row.against or '' }}</td>
                    <td class="text-right">{{ fmt_money(row.debit, currency=currency) if row.debit else '' }}</td>
                    <td class="text-right">{{ fmt_money(row.credit, currency=currency) if row.credit else '' }}</td>
                    <td class="text-right">{{ fmt_money(row.balance, currency=currency) }}</td>
                    <td>{{ row.remarks or '' }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <div class="footer">
            Generated on {{ generated_on }} &middot; System-generated bank statement. Please verify against original bank records.
        </div>
    </body>
    </html>
    """