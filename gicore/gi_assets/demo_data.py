# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT
"""Demo data for GI Assets, driven by buttons in Equipment Settings.

create_demo_data()  builds a small, realistic data set that exercises every part of the module
                    (categories, units, stock, kit, issue / transfer / return, a damage incident,
                    a draft handover and a request) using two EXISTING active employees.
delete_demo_data()  removes everything the demo created, plus anything that was later created
                    against the demo categories or demo equipment.

Everything the demo creates is tracked in Equipment Settings (demo_data_log) so the cleanup is exact.
Nothing the user created outside the demo categories is ever touched.
"""

import json

import frappe
from frappe import _
from frappe.utils import add_days, cint, nowdate

ALLOWED_ROLES = ("System Manager", "Equipment Manager")

CAT_LAPTOP = "Demo Laptop"
CAT_PHONE = "Demo Mobile Phone"
CAT_MOUSE = "Demo Mouse"
CAT_KEYBOARD = "Demo Keyboard"
KIT_NAME = "Demo Kit - Standard"
DEMO_CATEGORIES = (CAT_LAPTOP, CAT_PHONE, CAT_MOUSE, CAT_KEYBOARD)

# 1x1 transparent PNG, enough to satisfy the "signature required" rule on demo handovers
DEMO_SIGNATURE = (
	"data:image/png;base64,"
	"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
@frappe.whitelist()
def create_demo_data():
	frappe.only_for(ALLOWED_ROLES)

	if cint(frappe.db.get_single_value("Equipment Settings", "demo_data_created")):
		frappe.throw(_("Demo data already exists. Delete it first."))

	clashes = [c for c in DEMO_CATEGORIES if frappe.db.exists("Equipment Category", c)]
	if frappe.db.exists("Equipment Kit", KIT_NAME):
		clashes.append(KIT_NAME)
	if clashes:
		frappe.throw(
			_("These records already exist and would clash with the demo data: {0}. Rename or delete them first.").format(
				", ".join(frappe.bold(c) for c in clashes)
			)
		)

	company, emp_a, emp_b = _pick_employees()
	site = _pick_site()
	created = []

	def make(values, submit=False):
		doc = frappe.get_doc(values)
		doc.flags.ignore_permissions = True
		doc.insert()
		if submit:
			doc.submit()
		created.append([doc.doctype, doc.name])
		return doc

	frappe.flags.in_demo_data = True  # silences employee emails
	try:
		# --- categories -------------------------------------------------------------------
		make(
			{
				"doctype": "Equipment Category",
				"category_name": CAT_LAPTOP,
				"tracking_type": "Serialized",
				"default_accessories": "Charger, Laptop bag",
				"description": "Demo data",
			}
		)
		make({"doctype": "Equipment Category", "category_name": CAT_PHONE, "tracking_type": "Serialized", "description": "Demo data"})
		make({"doctype": "Equipment Category", "category_name": CAT_MOUSE, "tracking_type": "Quantity", "description": "Demo data"})
		make({"doctype": "Equipment Category", "category_name": CAT_KEYBOARD, "tracking_type": "Quantity", "description": "Demo data"})

		# --- serialized units -------------------------------------------------------------
		def unit(category, name, serial, brand, model, warranty_days, cost, **extra):
			values = {
				"doctype": "Equipment",
				"equipment_name": name,
				"category": category,
				"serial_no": serial,
				"brand": brand,
				"model": model,
				"condition": "New",
				"company": company,
				"purchase_date": add_days(nowdate(), -150),
				"purchase_cost": cost,
				"warranty_expiry": add_days(nowdate(), warranty_days),
				"remarks": "Demo data",
			}
			if site:
				values["site"] = site
			values.update(extra)
			return make(values)

		l1 = unit(CAT_LAPTOP, "Dell Latitude 5440", "DEMO-LT-001", "Dell", "Latitude 5440", 400, 4200)
		l2 = unit(CAT_LAPTOP, "Lenovo ThinkPad T14", "DEMO-LT-002", "Lenovo", "ThinkPad T14", 20, 4600)  # warranty about to expire
		l3 = unit(CAT_LAPTOP, "HP ProBook 450", "DEMO-LT-003", "HP", "ProBook 450 G10", 200, 3500)
		unit(CAT_LAPTOP, "Dell Latitude 5440", "DEMO-LT-004", "Dell", "Latitude 5440", -30, 4200)  # warranty expired
		p1 = unit(CAT_PHONE, "Samsung Galaxy A54", "DEMO-PH-001", "Samsung", "Galaxy A54", 300, 1300, imei="350000000000011")
		unit(CAT_PHONE, "Samsung Galaxy A54", "DEMO-PH-002", "Samsung", "Galaxy A54", 300, 1300, imei="350000000000029")

		# --- quantity stock ---------------------------------------------------------------
		for category, qty in ((CAT_MOUSE, 20), (CAT_KEYBOARD, 15)):
			values = {
				"doctype": "Equipment Stock Entry",
				"entry_type": "Receipt",
				"posting_date": nowdate(),
				"company": company,
				"category": category,
				"qty": qty,
				"reference": "DEMO-PO-001",
				"remarks": "Demo data",
			}
			if site:
				values["site"] = site
			make(values, submit=True)

		# --- standard kit (disabled if it would hijack a real kit) -------------------------
		designation, department = emp_a.designation, emp_a.department
		if designation or department:
			conflict = (
				frappe.db.exists("Equipment Kit", {"enabled": 1, "designation": designation})
				if designation
				else frappe.db.exists("Equipment Kit", {"enabled": 1, "department": department})
			)
			make(
				{
					"doctype": "Equipment Kit",
					"kit_name": KIT_NAME,
					"enabled": 0 if conflict else 1,
					"designation": designation,
					"department": None if designation else department,
					"items": [
						{"category": CAT_LAPTOP, "qty": 1},
						{"category": CAT_MOUSE, "qty": 1},
						{"category": CAT_KEYBOARD, "qty": 1},
					],
				}
			)

		# --- handovers --------------------------------------------------------------------
		def handover(kind, employee, items, from_employee=None, submit=True, remarks="Demo data"):
			values = {
				"doctype": "Equipment Handover",
				"handover_type": kind,
				"employee": employee,
				"from_employee": from_employee,
				"company": company,
				"posting_date": nowdate(),
				"handed_by": frappe.session.user,
				"employee_signature": DEMO_SIGNATURE,
				"remarks": remarks,
				"items": items,
			}
			if site:
				values["site"] = site
			return make(values, submit=submit)

		def row(category, equipment=None, qty=1, **extra):
			values = {"category": category, "equipment": equipment, "qty": qty, "condition_out": "New"}
			values.update(extra)
			return values

		# 1. employee A gets a laptop, a mouse and a keyboard
		handover(
			"Issue",
			emp_a.name,
			[
				row(CAT_LAPTOP, l1.name, accessories="Charger, Laptop bag"),
				row(CAT_MOUSE),
				row(CAT_KEYBOARD),
			],
		)
		# 2. employee B gets a laptop and a phone
		handover("Issue", emp_b.name, [row(CAT_LAPTOP, l2.name, accessories="Charger"), row(CAT_PHONE, p1.name)])
		# 3. the phone moves from B to A
		handover("Transfer", emp_a.name, [row(CAT_PHONE, p1.name, condition_out="Good")], from_employee=emp_b.name)
		# 4. B returns the laptop damaged -> unit In Repair + damage incident (open)
		handover(
			"Return",
			emp_b.name,
			[
				{
					"category": CAT_LAPTOP,
					"equipment": l2.name,
					"qty": 1,
					"return_result": "Damaged",
					"condition_in": "Damaged",
					"remarks": "Cracked screen (demo)",
				}
			],
		)
		# 5. A returns the keyboard in good condition -> quantity returns to store
		handover(
			"Return",
			emp_a.name,
			[{"category": CAT_KEYBOARD, "qty": 1, "return_result": "Returned OK", "condition_in": "Good"}],
		)
		# 6. a draft issue left open for the user to complete
		handover("Issue", emp_b.name, [row(CAT_LAPTOP, l3.name)], submit=False, remarks="Demo data (draft: open it and submit)")

		# --- request ----------------------------------------------------------------------
		make(
			{
				"doctype": "Equipment Request",
				"employee": emp_a.name,
				"company": company,
				"request_date": nowdate(),
				"request_type": "Replacement",
				"category": CAT_LAPTOP,
				"qty": 1,
				"required_by": add_days(nowdate(), 7),
				"justification": "Demo data: laptop battery no longer holds charge.",
			}
		)
	finally:
		frappe.flags.in_demo_data = False

	# only reached when everything above succeeded (an error rolls the whole request back)
	frappe.db.set_single_value("Equipment Settings", "demo_data_log", json.dumps(created))
	frappe.db.set_single_value("Equipment Settings", "demo_data_created", 1)

	counts = {}
	for doctype, _name in created:
		counts[doctype] = counts.get(doctype, 0) + 1
	return {"employees": [emp_a.employee_name or emp_a.name, emp_b.employee_name or emp_b.name], "counts": counts}


def _pick_employees():
	"""Two active employees of the same company (the demo moves equipment between them)."""
	rows = frappe.get_all(
		"Employee",
		filters={"status": "Active"},
		fields=["name", "employee_name", "company", "designation", "department"],
		order_by="creation asc",
		limit=500,
	)
	by_company = {}
	for r in rows:
		by_company.setdefault(r.company, []).append(r)
	for company, employees in by_company.items():
		if len(employees) >= 2:
			return company, employees[0], employees[1]
	frappe.throw(_("Demo data needs at least two Active employees in the same company."))


def _pick_site():
	settings_site = frappe.db.get_single_value("Equipment Settings", "default_site")
	if settings_site:
		return settings_site
	branches = frappe.get_all("Branch", pluck="name", order_by="creation asc", limit=1)
	return branches[0] if branches else None


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------
@frappe.whitelist()
def delete_demo_data():
	frappe.only_for(ALLOWED_ROLES)

	log = json.loads(frappe.db.get_single_value("Equipment Settings", "demo_data_log") or "[]")
	if not log and not cint(frappe.db.get_single_value("Equipment Settings", "demo_data_created")):
		frappe.throw(_("There is no demo data to delete."))

	tracked = {}
	for doctype, name in log:
		tracked.setdefault(doctype, set()).add(name)

	cats = [c for c in DEMO_CATEGORIES if frappe.db.exists("Equipment Category", c)]
	equipment = set(tracked.get("Equipment", ()))
	if cats:
		equipment.update(frappe.get_all("Equipment", filters={"category": ["in", cats]}, pluck="name"))

	handovers = set(tracked.get("Equipment Handover", ()))
	incidents = set(tracked.get("Equipment Incident", ()))
	stock_entries = set(tracked.get("Equipment Stock Entry", ()))
	requests = set(tracked.get("Equipment Request", ()))

	# anything created later against demo categories / demo units is demo too
	if cats:
		handovers.update(
			frappe.db.sql_list(
				"select distinct parent from `tabEquipment Handover Item` "
				"where parenttype = 'Equipment Handover' and category in %(c)s",
				{"c": tuple(cats)},
			)
		)
		incidents.update(frappe.get_all("Equipment Incident", filters={"category": ["in", cats]}, pluck="name"))
		stock_entries.update(frappe.get_all("Equipment Stock Entry", filters={"category": ["in", cats]}, pluck="name"))
		requests.update(frappe.get_all("Equipment Request", filters={"category": ["in", cats]}, pluck="name"))
	if equipment:
		incidents.update(frappe.get_all("Equipment Incident", filters={"equipment": ["in", list(equipment)]}, pluck="name"))

	removed = {}

	def drop(doctype, names, submitted=False):
		for name in sorted(names):
			if not frappe.db.exists(doctype, name):
				continue
			if submitted and frappe.db.get_value(doctype, name, "docstatus") == 1:
				# a cancelled document can be deleted; going through cancel() would trip the
				# "later movement exists" guard, which is irrelevant when everything is removed
				frappe.db.set_value(doctype, name, "docstatus", 2, update_modified=False)
			frappe.delete_doc(doctype, name, force=1, ignore_permissions=True, delete_permanently=True)
			removed[doctype] = removed.get(doctype, 0) + 1

	frappe.flags.in_demo_cleanup = True  # lets Equipment Incident.on_trash through
	try:
		drop("Equipment Incident", incidents)
		drop("Equipment Handover", handovers, submitted=True)
		drop("Equipment Request", requests, submitted=True)
		drop("Equipment Stock Entry", stock_entries, submitted=True)

		if cats:
			removed["Equipment Ledger"] = frappe.db.count("Equipment Ledger", {"category": ["in", cats]})
			frappe.db.delete("Equipment Ledger", {"category": ["in", cats]})

		drop("Equipment", equipment)
		drop("Equipment Kit", tracked.get("Equipment Kit", ()))
		drop("Equipment Category", cats)
	finally:
		frappe.flags.in_demo_cleanup = False

	frappe.db.set_single_value("Equipment Settings", "demo_data_log", "")
	frappe.db.set_single_value("Equipment Settings", "demo_data_created", 0)
	return {"counts": removed}
