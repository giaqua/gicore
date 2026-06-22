"""
EOSB / Gratuity Engine — Saudi Labor Law (Articles 84-87)
-----------------------------------------------------------
1. calculate_eosb()      -> exact gratuity due on a specific exit, given
                            exit type and service duration.
2. accrue_monthly_eosb() -> monthly provisioning job that books the
                            accruing liability into the GL, so EOSB
                            doesn't hit the books as a year-end shock.

LAW SUMMARY THIS IS BUILT ON (confirm against current MHRSD guidance
before relying on it for actual settlements):
  - Base gratuity = 0.5 month's wage per year for first 5 years,
                    + 1.0 month's wage per year after that.
  - Employer-initiated termination (not for cause): 100% of base.
  - Termination for cause (Art. 80 grounds): 0% — forfeited.
  - Employee resignation:
        < 2 years service   -> 0%
        2 to < 5 years       -> 1/3 of base
        5 to < 10 years      -> 2/3 of base
        >= 10 years           -> 100% of base
  - Contract expiry (fixed-term, not renewed) / death / retirement
    are generally treated as 100% of base, same as employer-initiated.

Wage basis = last basic salary + housing allowance (the components
generally treated as "fixed wage" for gratuity purposes — variable
bonuses/commissions are typically excluded, but confirm this against
your specific contracts/legal counsel since practice varies).

Drop into a custom app, e.g.:
  your_app/your_app/eosb/engine.py
"""

import frappe
from frappe.utils import flt, date_diff, getdate, nowdate, add_months

# ---------------------------------------------------------------------
# CONFIGURATION
# ---------------------------------------------------------------------

# Salary components counted as "fixed wage" for gratuity purposes.
WAGE_BASIS_COMPONENTS = ["Basic Salary", "Basic", "Housing Allowance","Basic GA", "Housing", "Housing GA"]

# GL accounts used by the monthly accrual job — set per company.
# TODO: replace with your real Chart of Accounts entries.
ACCRUAL_ACCOUNTS = {
    "Default Company": {
        "expense_account": "EOSB Expense - Default Company",
        "liability_account": "Provision for EOSB - Default Company",
    }
}

DAYS_PER_YEAR = 365.0


# ---------------------------------------------------------------------
# CORE CALCULATION
# ---------------------------------------------------------------------

def _years_of_service(joining_date, as_of_date):
    days = date_diff(getdate(as_of_date), getdate(joining_date))
    return max(days, 0) / DAYS_PER_YEAR


def _base_gratuity_months(years):
    first_five = min(years, 5)
    remaining = max(years - 5, 0)
    return (first_five * 0.5) + (remaining * 1.0)


def _resignation_factor(years):
    if years < 2:
        return 0.0
    elif years < 5:
        return 1 / 3
    elif years < 10:
        return 2 / 3
    return 1.0


EXIT_TYPE_FACTORS = {
    "employer_termination": lambda years: 1.0,
    "employer_termination_for_cause": lambda years: 0.0,
    "contract_expiry": lambda years: 1.0,
    "death_or_retirement": lambda years: 1.0,
    "resignation": _resignation_factor,
}


def _monthly_wage_basis(employee_id):
    """Latest submitted Salary Slip, summing configured wage components."""
    slip_name = frappe.get_all(
        "Salary Slip",
        filters={"employee": employee_id, "docstatus": 1},
        order_by="end_date desc",
        limit=1,
        pluck="name",
    )
    if not slip_name:
        frappe.throw(f"No submitted Salary Slip found for employee {employee_id} to derive wage basis.")

    slip = frappe.get_doc("Salary Slip", slip_name[0])
    total = sum(flt(row.amount) for row in slip.earnings if row.salary_component in WAGE_BASIS_COMPONENTS)
    return total


@frappe.whitelist()
def calculate_eosb(employee, exit_type, exit_date=None):
    """
    Returns a full breakdown of gratuity due for a given employee and
    exit type. exit_type must be one of EXIT_TYPE_FACTORS keys.
    """
    if exit_type not in EXIT_TYPE_FACTORS:
        frappe.throw(f"Unknown exit_type '{exit_type}'. Valid: {list(EXIT_TYPE_FACTORS)}")

    emp = frappe.get_doc("Employee", employee)
    exit_date = getdate(exit_date) if exit_date else getdate(nowdate())

    years = _years_of_service(emp.date_of_joining, exit_date)
    base_months = _base_gratuity_months(years)
    factor = EXIT_TYPE_FACTORS[exit_type](years)
    wage_basis = _monthly_wage_basis(employee)

    gratuity_amount = wage_basis * base_months * factor

    return {
        "employee": employee,
        "employee_name": emp.employee_name,
        "date_of_joining": str(emp.date_of_joining),
        "exit_date": str(exit_date),
        "years_of_service": round(years, 3),
        "monthly_wage_basis": round(wage_basis, 2),
        "base_gratuity_months": round(base_months, 4),
        "exit_type": exit_type,
        "applicable_factor": round(factor, 4),
        "gratuity_amount": round(gratuity_amount, 2),
    }


# ---------------------------------------------------------------------
# MONTHLY ACCRUAL (PROVISIONING)
# ---------------------------------------------------------------------
#
# Design choice: accrue at the FULL (employer-termination) rate every
# month, regardless of how the employee might eventually exit. This is
# the conservative/standard provisioning approach — it means the
# liability on the books always covers worst-case exposure, and the
# resignation discount (if it ends up applying) is simply released as
# a gain at actual settlement time rather than guessed at monthly.

def _monthly_accrual_rate(years_to_date):
    return (1 / 12) if years_to_date >= 5 else (0.5 / 12)


@frappe.whitelist()
def accrue_monthly_eosb(company, posting_date=None):
    """
    Computes this month's EOSB accrual for every active employee in
    `company` and posts a single consolidated Journal Entry. Intended
    to run as a monthly scheduled job (see hooks.py snippet below).
    """
    posting_date = getdate(posting_date) if posting_date else getdate(nowdate())
    accounts = ACCRUAL_ACCOUNTS.get(company)
    if not accounts:
        frappe.throw(f"No ACCRUAL_ACCOUNTS configured for company '{company}'.")

    employees = frappe.get_all(
        "Employee",
        filters={"company": company, "status": "Active"},
        fields=["name", "date_of_joining"],
    )

    total_accrual = 0.0
    skipped = []

    for emp in employees:
        try:
            wage_basis = _monthly_wage_basis(emp.name)
        except Exception:
            skipped.append(emp.name)
            continue

        years = _years_of_service(emp.date_of_joining, posting_date)
        rate = _monthly_accrual_rate(years)
        total_accrual += wage_basis * rate

    if total_accrual <= 0:
        frappe.msgprint("No accrual amount computed — check Salary Slip data for the period.")
        return None

    je = frappe.get_doc({
        "doctype": "Journal Entry",
        "voucher_type": "Journal Entry",
        "company": company,
        "posting_date": posting_date,
        "user_remark": f"EOSB monthly accrual — {posting_date.strftime('%B %Y')}",
        "accounts": [
            {
                "account": accounts["expense_account"],
                "debit_in_account_currency": total_accrual,
            },
            {
                "account": accounts["liability_account"],
                "credit_in_account_currency": total_accrual,
            },
        ],
    })
    je.insert(ignore_permissions=True)
    je.submit()

    if skipped:
        frappe.msgprint(
            f"Skipped {len(skipped)} employee(s) with no Salary Slip on record: {', '.join(skipped)}"
        )

    return {"journal_entry": je.name, "total_accrual": round(total_accrual, 2)}


# ---------------------------------------------------------------------
# hooks.py — register the scheduled job (add to your app's hooks.py):
#
# scheduler_events = {
#     "monthly": [
#         "your_app.eosb.engine.run_monthly_accrual_for_all_companies",
#     ]
# }
#
# def run_monthly_accrual_for_all_companies():
#     for company in ACCRUAL_ACCOUNTS:
#         accrue_monthly_eosb(company)
# ---------------------------------------------------------------------