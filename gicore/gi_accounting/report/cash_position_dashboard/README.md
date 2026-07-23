# Cash Position Dashboard — gicore / gi_accounting

Script Report giving a single, filter-driven view of:

1. **Cash Position** — live balance of every Bank/Cash account (account + company currency, % of total, linked Bank Account name, active/disabled status).
2. **Cash Flow Forecast** — Opening Balance → Expected Receipts (AR outstanding) → Expected Payments (AP outstanding) → Net Cash Flow → Projected Balance, bucketed Overdue / 0-7 / 8-30 / 31-60 / 61-90 / 90+ days from `as_on_date`.
3. **Historical Trend** — daily/weekly/monthly inflow, outflow, net change and running closing balance for the selected date range, driven off GL Entry.

KPI cards (report_summary) always show: Total Cash & Bank, Bank Balance, Cash in Hand, Projected Balance (30 days), Net Change (30 days), Active Accounts — regardless of which view is selected, so the dashboard feel stays consistent.

## Install

1. Confirm `gi_accounting` is registered in `gicore/gicore/modules.txt` as `Gi Accounting`. If not, add it and create the module's `__init__.py`.
2. Copy this `report/cash_position_dashboard/` folder into:
   `gicore/gicore/gi_accounting/report/cash_position_dashboard/`
3. Run:
   ```
   bench --site <sitename> migrate
   bench --site <sitename> clear-cache
   ```
4. Open **Cash Position Dashboard** from the Report list, or add it to a Workspace shortcut.

## Design notes / assumptions

- Bank/Cash accounts are detected via `Account.account_type in ('Bank', 'Cash')` with `is_group = 0`, scoped to the selected Company. Balances come straight from `GL Entry` (`sum(debit - credit)` up to `as_on_date`, `is_cancelled = 0`) rather than `get_balance_on`, matching the pattern used in `et_gl` for large-volume performance.
- Forecast uses `Sales Invoice` / `Purchase Invoice` `outstanding_amount` bucketed by `datediff(due_date, as_on_date)`. It intentionally does not include unbilled POs/SOs, Payment Entries against Journal Entries, or recurring payroll/loan schedules — flag if you want `employee_loans` or `gi_hr` payroll runs folded into the outflow side, since those live in separate doctypes with their own due-date logic.
- Historical Trend's weekly bucket uses MariaDB's `%x-%v` (ISO year-week) format; switch to `%Y-%u` if you prefer non-ISO week numbering.
- `get_forecast_data()` is called twice per request (once for the Forecast view's table, once for the KPI cards) — cheap here since it's aggregate SQL over Sales/Purchase Invoice, not a full transaction scan, but wrap with `frappe.cache()` (60s TTL) if this ends up on a high-traffic dashboard.
- Multi-currency: table shows both account-currency and company-currency balances; KPI cards and forecast are company-currency only. If you run true multi-currency treasury (not just SAR accounts under a SAR company), you'll want to add exchange-rate conversion on the forecast side too — currently it assumes AR/AP outstanding is already in company currency terms via ERPNext's standard outstanding_amount field.
- Permissions: Report is scoped to `Accounts Manager`, `Accounts User`, `System Manager` — adjust to your role setup (e.g. add a read-only `CFO`/`Owner` role if needed).
- Negative values (net change, projected balance, bucket totals) render in HM red (`#D50000`) via the JS formatter; everything else follows theme defaults.