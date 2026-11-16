# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT

import frappe
from frappe import _
from frappe.utils import flt, now_datetime

# Users holding any of these roles can see all custody records.
# Everyone else (plain employees) only sees records that belong to their own Employee.
PRIVILEGED_ROLES = {"System Manager", "Equipment Manager", "Equipment User", "HR Manager", "HR User"}


def get_settings():
	return frappe.get_single("Equipment Settings")


def default_company():
	return frappe.defaults.get_user_default("Company") or frappe.db.get_default("company")


def get_session_employee(user=None):
	user = user or frappe.session.user
	return frappe.db.get_value("Employee", {"user_id": user}, "name")


def is_privileged(user=None):
	user = user or frappe.session.user
	if user == "Administrator":
		return True
	return bool(PRIVILEGED_ROLES & set(frappe.get_roles(user)))


def get_employee_email(employee):
	row = frappe.db.get_value(
		"Employee",
		employee,
		["prefered_email", "company_email", "personal_email", "user_id"],
		as_dict=True,
	)
	if not row:
		return None
	return row.prefered_email or row.company_email or row.user_id or row.personal_email


# ---------------------------------------------------------------------------
# Ledger
# ---------------------------------------------------------------------------
def post_ledger(
	movement_type,
	category,
	qty,
	stock_effect=0,
	custody_effect=0,
	employee=None,
	equipment=None,
	site=None,
	company=None,
	condition=None,
	reference_doctype=None,
	reference_name=None,
	reference_row=None,
	is_reversal=0,
	remarks=None,
):
	"""Append one immutable row to the Equipment Ledger.

	stock_effect   - change in units sitting in the store (In Stock)
	custody_effect - change in units held by `employee`
	"""
	doc = frappe.get_doc(
		{
			"doctype": "Equipment Ledger",
			"posting_datetime": now_datetime(),
			"movement_type": movement_type,
			"category": category,
			"equipment": equipment,
			"employee": employee,
			"qty": flt(qty),
			"stock_effect": flt(stock_effect),
			"custody_effect": flt(custody_effect),
			"site": site,
			"company": company,
			"condition": condition,
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"reference_row": reference_row,
			"is_reversal": 1 if is_reversal else 0,
			"remarks": remarks,
		}
	)
	doc.flags.from_controller = True
	doc.flags.ignore_permissions = True
	doc.insert()
	return doc


def reverse_ledger_entries(reference_doctype, reference_name, remarks=None):
	"""Post a mirror-image entry for every ledger row created by a document (used on cancel)."""
	entries = frappe.get_all(
		"Equipment Ledger",
		filters={
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"is_reversal": 0,
		},
		fields=[
			"movement_type",
			"category",
			"qty",
			"stock_effect",
			"custody_effect",
			"employee",
			"equipment",
			"site",
			"company",
			"condition",
			"reference_row",
		],
		order_by="creation desc",
	)
	for e in entries:
		post_ledger(
			movement_type=e.movement_type,
			category=e.category,
			qty=e.qty,
			stock_effect=-flt(e.stock_effect),
			custody_effect=-flt(e.custody_effect),
			employee=e.employee,
			equipment=e.equipment,
			site=e.site,
			company=e.company,
			condition=e.condition,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			reference_row=e.reference_row,
			is_reversal=1,
			remarks=remarks or _("Reversal of cancelled {0}").format(reference_name),
		)


# ---------------------------------------------------------------------------
# Balances
# ---------------------------------------------------------------------------
def get_stock_balance(category, site=None, company=None):
	"""Units of `category` currently available in the store."""
	conditions = ["category = %(category)s"]
	values = {"category": category}
	if site:
		conditions.append("site = %(site)s")
		values["site"] = site
	if company:
		conditions.append("company = %(company)s")
		values["company"] = company
	result = frappe.db.sql(
		"select sum(stock_effect) from `tabEquipment Ledger` where " + " and ".join(conditions),
		values,
	)
	return flt(result[0][0]) if result else 0.0


def get_custody_balance(category, employee):
	"""Units of `category` currently held by `employee`."""
	result = frappe.db.sql(
		"""select sum(custody_effect) from `tabEquipment Ledger`
		where category = %s and employee = %s""",
		(category, employee),
	)
	return flt(result[0][0]) if result else 0.0


def get_employee_custody(employee):
	"""Everything an employee currently holds.

	Returns {"serialized": [...Equipment rows...], "quantity": [{category, qty}, ...]}
	"""
	serialized = frappe.get_all(
		"Equipment",
		filters={"current_custodian": employee, "status": "Issued"},
		fields=["name", "equipment_name", "category", "serial_no", "condition"],
		order_by="category, name",
	)
	quantity = frappe.db.sql(
		"""select l.category, sum(l.custody_effect) as qty
		from `tabEquipment Ledger` l
		inner join `tabEquipment Category` c on c.name = l.category
		where l.employee = %s and c.tracking_type = 'Quantity'
		group by l.category
		having sum(l.custody_effect) > 0
		order by l.category""",
		employee,
		as_dict=True,
	)
	return frappe._dict(serialized=serialized, quantity=quantity)


def has_open_custody(employee):
	custody = get_employee_custody(employee)
	return bool(custody.serialized or custody.quantity)


def custody_items_html(custody):
	"""Small HTML table of an employee's custody, used in emails and error messages."""
	rows = []
	for d in custody.serialized:
		rows.append(
			f"<tr><td>{frappe.utils.escape_html(d.category)}</td>"
			f"<td>{frappe.utils.escape_html(d.equipment_name or d.name)}</td>"
			f"<td>{frappe.utils.escape_html(d.serial_no or '')}</td><td>1</td></tr>"
		)
	for d in custody.quantity:
		rows.append(
			f"<tr><td>{frappe.utils.escape_html(d.category)}</td><td>-</td><td>-</td>"
			f"<td>{flt(d.qty):g}</td></tr>"
		)
	if not rows:
		return ""
	return (
		"<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"
		"<tr><th>Category</th><th>Equipment</th><th>Serial No</th><th>Qty</th></tr>"
		+ "".join(rows)
		+ "</table>"
	)


def handover_items_html(items):
	rows = []
	for d in items:
		rows.append(
			f"<tr><td>{frappe.utils.escape_html(d.category or '')}</td>"
			f"<td>{frappe.utils.escape_html(d.equipment_name or d.equipment or '')}</td>"
			f"<td>{frappe.utils.escape_html(d.serial_no or '')}</td><td>{flt(d.qty):g}</td></tr>"
		)
	return (
		"<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse'>"
		"<tr><th>Category</th><th>Equipment</th><th>Serial No</th><th>Qty</th></tr>"
		+ "".join(rows)
		+ "</table>"
	)
