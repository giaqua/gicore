import frappe
from frappe import _
from frappe.utils import getdate


def execute(filters=None):
    filters = frappe._dict(filters or {})
    if filters.from_date and filters.to_date and getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be after To Date"))

    data = []
    ptype = filters.get("petty_cash_type")
    if not ptype or ptype == "Journal Entry":
        data += get_journal_entry_data(filters)
    if (not ptype or ptype == "Purchase Invoice") and filters.get("party_type") in (None, "", "Supplier"):
        data += get_purchase_invoice_data(filters)

    data.sort(key=lambda d: (d.get("date") or "", d.get("transaction") or ""))

    group_by = GROUP_FIELDS.get(filters.get("group_by"))
    if group_by:
        return get_grouped_columns(group_by), group_data(data, group_by)
    return get_columns(), data


GROUP_FIELDS = {
    "Project": "project",
    "Expense Account": "expense_account",
    "Petty Cash Account": "petty_cash_account",
}


def get_grouped_columns(group_by):
    meta = {
        "project": {"label": _("Project"), "fieldtype": "Link", "options": "Project"},
        "expense_account": {"label": _("Expense Account"), "fieldtype": "Link", "options": "Account"},
        "petty_cash_account": {"label": _("Petty Cash Account"), "fieldtype": "Link", "options": "Account"},
    }[group_by]
    return [
        {**meta, "fieldname": group_by, "width": 280},
        {"label": _("No. of Lines"), "fieldname": "count", "fieldtype": "Int", "width": 110},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 140},
    ]


def group_data(data, group_by):
    groups = {}
    for d in data:
        key = d.get(group_by) or ""
        g = groups.setdefault(key, {group_by: key, "count": 0, "amount": 0.0})
        g["count"] += 1
        g["amount"] += d.get("amount") or 0
    return sorted(groups.values(), key=lambda g: g[group_by])


def get_columns():
    return [
        {"label": _("Project"), "fieldname": "project", "fieldtype": "Link", "options": "Project", "width": 140},
        {"label": _("Petty Cash Type"), "fieldname": "petty_cash_type", "fieldtype": "Data", "width": 130},
        {"label": _("Expense Account"), "fieldname": "expense_account", "fieldtype": "Link", "options": "Account", "width": 220},
        {"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
        {"label": _("Party"), "fieldname": "party", "fieldtype": "Data", "width": 170},
        {"label": _("Date"), "fieldname": "date", "fieldtype": "Date", "width": 100},
        {"label": _("Transaction"), "fieldname": "transaction", "fieldtype": "Dynamic Link", "options": "petty_cash_type", "width": 160},
        {"label": _("Petty Cash Account"), "fieldname": "petty_cash_account", "fieldtype": "Link", "options": "Account", "width": 220},
    ]


def get_journal_entry_data(f):
    """Expense (debit) rows of Journal Entries that are paid from a Cash-type account."""
    conds, values = [], {}
    party_expr = "COALESCE(NULLIF(jea.party, ''), NULLIF(cash.party, ''))"

    if f.get("company"):
        conds.append("je.company = %(company)s"); values["company"] = f.company
    if f.get("from_date"):
        conds.append("je.posting_date >= %(from_date)s"); values["from_date"] = f.from_date
    if f.get("to_date"):
        conds.append("je.posting_date <= %(to_date)s"); values["to_date"] = f.to_date
    if f.get("account"):
        conds.append("cash.account = %(account)s"); values["account"] = f.account
    if f.get("project"):
        conds.append("jea.project = %(project)s"); values["project"] = f.project
    if f.get("party_type"):
        conds.append("COALESCE(NULLIF(jea.party_type, ''), NULLIF(cash.party_type, '')) = %(party_type)s")
        values["party_type"] = f.party_type
    if f.get("party"):
        conds.append(f"{party_expr} = %(party)s"); values["party"] = f.party

    where = (" AND " + " AND ".join(conds)) if conds else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            jea.project AS project,
            jea.account AS expense_account,
            (jea.debit - jea.credit) AS amount,
            {party_expr} AS party,
            je.posting_date AS date,
            je.name AS transaction,
            cash.account AS petty_cash_account
        FROM `tabJournal Entry` je
        INNER JOIN `tabJournal Entry Account` jea ON jea.parent = je.name
        INNER JOIN `tabAccount` exp ON exp.name = jea.account
        INNER JOIN (
            SELECT jc.parent, jc.account, jc.party, jc.party_type
            FROM `tabJournal Entry Account` jc
            INNER JOIN `tabAccount` ca ON ca.name = jc.account AND ca.account_type = 'Cash'
            WHERE jc.credit > 0
        ) cash ON cash.parent = je.name
        WHERE je.docstatus = 1
          AND jea.debit > 0
          AND exp.account_type != 'Cash'
          {where}
        """,
        values,
        as_dict=True,
    )
    for r in rows:
        r["petty_cash_type"] = "Journal Entry"
    return rows


def get_purchase_invoice_data(f):
    """Purchase Invoices marked 'Is Paid' with a Cash-type Cash/Bank account."""
    conds, values = [], {}

    if f.get("company"):
        conds.append("pi.company = %(company)s"); values["company"] = f.company
    if f.get("from_date"):
        conds.append("pi.posting_date >= %(from_date)s"); values["from_date"] = f.from_date
    if f.get("to_date"):
        conds.append("pi.posting_date <= %(to_date)s"); values["to_date"] = f.to_date
    if f.get("account"):
        conds.append("pi.cash_bank_account = %(account)s"); values["account"] = f.account
    if f.get("project"):
        conds.append("COALESCE(NULLIF(pii.project, ''), NULLIF(pi.project, '')) = %(project)s")
        values["project"] = f.project
    if f.get("party"):
        conds.append("pi.supplier = %(party)s"); values["party"] = f.party

    where = (" AND " + " AND ".join(conds)) if conds else ""

    rows = frappe.db.sql(
        f"""
        SELECT
            COALESCE(NULLIF(pii.project, ''), NULLIF(pi.project, '')) AS project,
            pii.expense_account AS expense_account,
            pii.base_net_amount AS amount,
            COALESCE(NULLIF(pi.supplier_name, ''), pi.supplier) AS party,
            pi.posting_date AS date,
            pi.name AS transaction,
            pi.cash_bank_account AS petty_cash_account
        FROM `tabPurchase Invoice` pi
        INNER JOIN `tabPurchase Invoice Item` pii ON pii.parent = pi.name
        INNER JOIN `tabAccount` acc ON acc.name = pi.cash_bank_account AND acc.account_type = 'Cash'
        WHERE pi.docstatus = 1
          AND pi.is_paid = 1
          {where}
        """,
        values,
        as_dict=True,
    )
    for r in rows:
        r["petty_cash_type"] = "Purchase Invoice"
    return rows