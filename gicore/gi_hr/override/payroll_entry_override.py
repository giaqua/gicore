# your_app/payroll/payroll_entry_override.py
import frappe
from frappe.utils import flt
from hrms.payroll.doctype.payroll_entry.payroll_entry import PayrollEntry


class CustomPayrollEntry(PayrollEntry):

    def get_component_party(self, salary_component, employee):
        """Returns (party_type, party) if the component is flagged, else (None, None).
        Party is always resolved from the current row's employee — never fixed on the
        component, since one component is shared across all employees."""
        flags = frappe.get_cached_value(
            "Salary Component",
            salary_component,
            ["custom_apply_party", "custom_party_type"],
            as_dict=True,
        )
        if flags and flags.custom_apply_party:
            party_type = flags.custom_party_type or "Employee"
            party = employee if party_type == "Employee" else None
            return party_type, party
        return None, None

    def get_salary_component_total(self, component_type=None, employee_wise_accounting_enabled=False):
        salary_components = self.get_salary_components(component_type)
        if not salary_components:
            return

        component_dict = {}

        for item in salary_components:
            if not self.should_add_component_to_accrual_jv(component_type, item):
                continue

            employee_cost_centers = self.get_payroll_cost_centers_for_employee(
                item.employee, item.salary_structure
            )
            employee_advance = self.get_advance_deduction(component_type, item)

            # Only resolve/inject party when employee-wise accounting is OFF.
            # When it's ON, party is already carried at the payable-account level,
            # so we fall back to stock behavior here to avoid double-tracking party.
            if employee_wise_accounting_enabled:
                party_type, party = None, None
            else:
                party_type, party = self.get_component_party(item.salary_component, item.employee)

            for cost_center, percentage in employee_cost_centers.items():
                amount_against_cost_center = flt(item.amount) * percentage / 100

                if employee_advance:
                    self.add_advance_deduction_entry(
                        item, amount_against_cost_center, cost_center, employee_advance
                    )
                else:
                    key = (item.salary_component, cost_center, party_type, party)
                    component_dict[key] = component_dict.get(key, 0) + amount_against_cost_center

                if employee_wise_accounting_enabled:
                    self.set_employee_based_payroll_payable_entries(
                        component_type, item.employee, amount_against_cost_center
                    )

        return self.get_account(component_dict=component_dict)

    def get_account(self, component_dict=None):
        account_dict = {}
        for key, amount in component_dict.items():
            component, cost_center, party_type, party = key
            account = self.get_salary_component_account(component)
            accounting_key = (account, cost_center, party_type, party)
            account_dict[accounting_key] = account_dict.get(accounting_key, 0) + amount
        return account_dict

    def get_payable_amount_for_earnings_and_deductions(
        self, accounts, earnings, deductions, currencies, company_currency,
        accounting_dimensions, precision, payable_amount,
    ):
        for acc_key, amount in earnings.items():
            account, cost_center, party_type, party = acc_key
            payable_amount = self.get_accounting_entries_and_payable_amount(
                account, cost_center or self.cost_center, amount, currencies, company_currency,
                payable_amount, accounting_dimensions, precision,
                entry_type="debit", accounts=accounts, party=party, party_type=party_type,
            )

        for acc_key, amount in deductions.items():
            account, cost_center, party_type, party = acc_key
            payable_amount = self.get_accounting_entries_and_payable_amount(
                account, cost_center or self.cost_center, amount, currencies, company_currency,
                payable_amount, accounting_dimensions, precision,
                entry_type="credit", accounts=accounts, party=party, party_type=party_type,
            )

        return payable_amount

    def get_accounting_entries_and_payable_amount(
        self, account, cost_center, amount, currencies, company_currency, payable_amount,
        accounting_dimensions, precision, entry_type="credit", party=None, party_type=None,
        accounts=None, reference_type=None, reference_name=None, is_advance=None,
    ):
        exchange_rate, amt = self.get_amount_and_exchange_rate_for_journal_entry(
            account, amount, company_currency, currencies
        )

        row = {
            "account": account,
            "exchange_rate": flt(exchange_rate),
            "cost_center": cost_center,
            "project": self.project,
        }

        if entry_type == "debit":
            payable_amount += flt(amount, precision)
            row.update({"debit_in_account_currency": flt(amt, precision)})
        elif entry_type == "credit":
            payable_amount -= flt(amount, precision)
            row.update({"credit_in_account_currency": flt(amt, precision)})
        else:
            row.update({
                "credit_in_account_currency": flt(amt, precision),
                "reference_type": self.doctype,
                "reference_name": self.name,
            })

        if party:
            row.update({"party_type": party_type or "Employee", "party": party})

        if reference_type:
            row.update({
                "reference_type": reference_type,
                "reference_name": reference_name,
                "is_advance": is_advance,
            })

        self.update_accounting_dimensions(row, accounting_dimensions)

        if amt:
            accounts.append(row)

        return payable_amount