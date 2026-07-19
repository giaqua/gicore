# Copyright (c) 2026
import frappe
from frappe import _
from frappe.utils import flt


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
    conditions = get_conditions(filters)

    opening_balance = get_opening_balance(filters)

    gl_entries = frappe.db.sql(
        """
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
            {conditions}
        order by gl.posting_date asc, gl.creation asc
        """.format(conditions=conditions),
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


def get_conditions(filters):
    conditions = ""

    if filters.get("party_type"):
        conditions += " and gl.party_type = %(party_type)s"
    if filters.get("party"):
        conditions += " and gl.party = %(party)s"
    if filters.get("voucher_no"):
        conditions += " and gl.voucher_no = %(voucher_no)s"

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