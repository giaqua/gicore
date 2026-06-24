"""
Mudad / WPS Wage File Generator
--------------------------------
Generates the monthly wage file (CSV) for upload to the Mudad
Compliance System (mudad.com.sa), built from a submitted Payroll Entry.

IMPORTANT — before using in production:
1. Log in to mudad.com.sa (Compliance System) and download the current
   official wage file template. Confirm column names/order and update
   CSV_COLUMNS / the row-building logic below to match exactly — Mudad's
   CSV spec isn't published as open API docs and has changed before.
2. Update FIELD_MAP below to match your actual Employee custom field
   names for national ID / Iqama number and IBAN.
3. Update SALARY_COMPONENT_MAP to match your Salary Component names
   for Basic, Housing Allowance, etc. Anything in "earnings" not listed
   there falls into "Other Earnings" automatically.
4. If your establishment has 1,000+ employees, Mudad routes WPS through
   a direct bank subscription instead of the standard portal upload —
   this script targets the standard Compliance System path.

Drop this file into a custom app, e.g.:
  your_app/your_app/mudad/wage_file.py

Pair it with mudad_wage_file.js, which adds a button to Payroll Entry
that calls generate_mudad_wage_file().
"""

import csv
import io

import frappe
from frappe.utils import flt, getdate, nowdate

# ---------------------------------------------------------------------
# CONFIGURATION — adjust these to match your schema / Mudad template
# ---------------------------------------------------------------------

FIELD_MAP = {
    "national_id": "custom_id_number",   # Employee fieldname: Iqama / National ID
    "iban": "iban",                  # Employee fieldname: IBAN (24 chars, local bank)
}

SALARY_COMPONENT_MAP = {
    "basic": ["Basic Salary", "Basic","Basic GA"],
    "housing": ["Housing Allowance","Housing","Housing GA"],
}

# Confirm this order/naming against the template downloaded from the
# Mudad portal before going live.
CSV_COLUMNS = [
    "Employee Id/Iqama",       # Iqama / National ID
    "Employee Account No/IBAN",
    "Employee Name",
    "Bank Code",
    "Basic Salary",
    "Housing Allowance",
    "Other Allowance",
    "Deductions",
    "Total Amount",
]

WRITE_HEADER_ROW = True  # set False if the portal template expects no header

# ---------------------------------------------------------------------


@frappe.whitelist()
def generate_mudad_wage_file(payroll_entry):
    """
    Build the wage file CSV for all submitted Salary Slips under a
    Payroll Entry and attach it to that Payroll Entry as a File.
    Returns the file_url so the client script can open/download it.
    """
    pe = frappe.get_doc("Payroll Entry", payroll_entry)

    slip_names = frappe.get_all(
        "Salary Slip",
        filters={"payroll_entry": pe.name, "docstatus": 1},
        pluck="name",
    )

    if not slip_names:
        frappe.throw("No submitted Salary Slips found for this Payroll Entry.")

    rows = []
    total_net = 0

    for slip_name in slip_names:
        slip = frappe.get_doc("Salary Slip", slip_name)
        employee = frappe.get_doc("Employee", slip.employee)

        national_id = employee.get(FIELD_MAP["national_id"])
        print(f"Processing employee {employee.name}: National ID / Iqama = {national_id}")
        iban = employee.get(FIELD_MAP["iban"])
        bank_code = employee.get("custom_bank_code") or "000"  # default if not set

        if not national_id:
            frappe.throw(
                f"Missing National ID / Iqama for employee {slip.employee} "
                f"({slip.employee_name}) — required for the Mudad file."
            )
        if not iban:
            frappe.throw(
                f"Missing IBAN for employee {slip.employee} "
                f"({slip.employee_name}) — required for the Mudad file."
            )

        basic = 0.0
        housing = 0.0
        other_earnings = 0.0

        for row in slip.earnings:
            comp = row.salary_component
            amt = flt(row.amount)
            if comp in SALARY_COMPONENT_MAP["basic"]:
                basic += amt
            elif comp in SALARY_COMPONENT_MAP["housing"]:
                housing += amt
            else:
                other_earnings += amt

        deductions = sum(flt(d.amount) for d in slip.deductions)
        net_amount = flt(slip.net_pay)
        total_net += net_amount

        rows.append([
            national_id,
            iban,
            slip.employee_name,
            bank_code,
            f"{basic:.2f}",
            f"{housing:.2f}",
            f"{other_earnings:.2f}",
            f"{deductions:.2f}",
            f"{net_amount:.2f}",
        ])

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    if WRITE_HEADER_ROW:
        writer.writerow(CSV_COLUMNS)
    writer.writerows(rows)
    file_content = buffer.getvalue()

    posting_date = getdate(pe.posting_date) if pe.get("posting_date") else nowdate()
    file_name = f"Mudad-Wage-File-{pe.name}-{posting_date}.csv"

    file_doc = frappe.get_doc({
        "doctype": "File",
        "file_name": file_name,
        "attached_to_doctype": "Payroll Entry",
        "attached_to_name": pe.name,
        "content": file_content,
        "is_private": 1,
    })
    file_doc.insert(ignore_permissions=True)

    frappe.msgprint(
        f"Wage file generated: {len(rows)} employees, total net SAR {total_net:,.2f}. "
        f"Review the file before uploading to Mudad."
    )

    return file_doc.file_url