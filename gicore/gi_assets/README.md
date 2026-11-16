# HM Equipment Custody

Employee equipment custody (عهدة) for ERPNext / Frappe: laptops, mice, keyboards, phones and anything else you hand to an employee and take back.

It is a **standalone module**. It does not depend on the ERPNext Asset doctype. If finance also registers a unit as an Asset, you can link it with an optional field and optionally sync Asset Movements.

## Install (standalone version only - see INSTALL.md for gicore)

```bash
bench get-app /path/to/hm_equipment_custody      # or your git URL
bench --site your.site install-app hm_equipment_custody
bench --site your.site migrate
```

Requires `erpnext` and `hrms` (Employee, Branch, Additional Salary, Employee Separation).

## First-time setup

1. **Roles** (created automatically): `Equipment Manager` (IT manager), `Equipment User` (IT staff), `Equipment Line Manager` (approves requests). Assign them to users. Plain employees only need the standard `Employee` role.
2. **Equipment Settings**: default terms template, default branch, signature required, reminder period, deduction salary component, optional Asset sync.
3. **Equipment Category**: create categories and choose the tracking type.
   - `Serialized` - one Equipment record per unit (laptop, phone, monitor)
   - `Quantity` - tracked by count only (mouse, keyboard, cables)
4. **Opening inventory**
   - Serialized: import/create `Equipment` records. To record a laptop that is already with an employee, set *Current Custodian* while creating it (opening custody).
   - Quantity: create an `Equipment Stock Entry` (Receipt) per category and branch.
5. Optional: create **Equipment Kit** per designation/department (e.g. Sales Rep = Laptop + Mouse + Phone).

## DocTypes

| DocType | Purpose |
|---|---|
| Equipment | One record per serialized unit. `status` and `current_custodian` change only through handovers/incidents. Optional `linked_asset`. |
| Equipment Category | Classification + tracking type, default accessories, photo-on-return flag |
| Equipment Request | Employee request, approved by the workflow (Draft > Pending Manager > Pending IT > Approved > Fulfilled) |
| Equipment Handover | Submittable document for **Issue**, **Return**, **Transfer**, with signature and terms |
| Equipment Handover Item | Child table: equipment / category, qty, condition out/in, return result, photo |
| Equipment Ledger | Append-only audit trail (cancel posts reversing rows). Basis of all balances. |
| Equipment Incident | Damage / loss / theft, resolution, optional salary deduction (Additional Salary draft) |
| Equipment Kit / Kit Item | Standard kit by designation or department |
| Equipment Stock Entry | Receive or adjust quantity items |
| Equipment Settings | Single settings doctype |

## Rules the app enforces

- Custodian and status can only change through a **submitted** handover or incident.
- Can't issue what isn't In Stock, can't return/transfer what the employee doesn't hold, no negative quantity stock (configurable).
- Return rows record result: *Returned OK* (back to stock), *Damaged* (In Repair + incident), *Missing* (Lost + incident).
- Photo required on return for categories that ask for it; signature required before submit (configurable).
- Cancelling a handover is blocked if a later movement exists, otherwise it restores state and posts reversing ledger rows.
- Employee can't be set to *Left*, and Employee Separation / Full and Final Statement can't be submitted, while custody is open (configurable).
- Employees only see their own equipment, handovers, requests, incidents and ledger rows.

## Optional ERPNext Asset link

| Case | Behaviour |
|---|---|
| `linked_asset` empty | Custody works fully on its own |
| `linked_asset` set, *Sync to Asset Movement* off | Reference only |
| `linked_asset` set, sync on | Handover also creates/cancels Asset Movements (Issue / Receipt; transfer = Receipt + Issue). Needs *Asset Receipt Location* in settings. |

## Reports

Custody by Employee (printable clearance sheet) - Equipment Status Summary - Warranty Expiry - Left Employees With Custody - plus the Equipment Ledger list for full history of any unit.

## Scheduled jobs (daily)

- Every N months: email each employee their custody list to confirm.
- Mondays: digest to Equipment Managers (warranty expiring, left employees still holding equipment).

## Print format

`Equipment Handover Form` - bilingual (English / Arabic), items table, terms, employee signature and IT officer signature line.

## Notes

- Developed against Frappe/ERPNext v15 conventions. Review on a staging site before production, especially the optional Asset Movement sync.
- Workflow, print format and workspace are created on install only if missing, so UI edits survive `bench migrate`.
