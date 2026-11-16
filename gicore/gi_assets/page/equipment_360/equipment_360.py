# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT
"""Data for the Equipment 360 page: everything known about one unit, ready to chart."""

import frappe
from frappe import _
from frappe.utils import date_diff, flt, getdate, nowdate

from gicore.gi_assets import utils

OTHER = "Other"
GROUP = {"Issue": "Issue", "Return": "Return", "Transfer In": "Transfer"}


@frappe.whitelist()
def get_data(equipment):
	if not utils.is_privileged():
		frappe.throw(_("You are not permitted to open the Equipment 360 view."), frappe.PermissionError)
	frappe.has_permission("Equipment", "read", doc=equipment, throw=True)

	eq = frappe.get_doc("Equipment", equipment)
	today = getdate(nowdate())

	raw = frappe.get_all(
		"Equipment Ledger",
		filters={"equipment": equipment},
		fields=[
			"name", "posting_datetime", "movement_type", "employee", "qty", "stock_effect",
			"custody_effect", "reference_doctype", "reference_name", "reference_row",
			"is_reversal", "condition", "remarks",
		],
		order_by="posting_datetime asc, creation asc",
	)
	rows = drop_reversed(raw)

	emp_ids = {r.employee for r in rows if r.employee} | ({eq.current_custodian} if eq.current_custodian else set())
	incidents = frappe.get_all(
		"Equipment Incident",
		filters={"equipment": equipment},
		fields=[
			"name", "incident_type", "incident_date", "status", "resolution", "employee",
			"estimated_cost", "deduction_amount", "employee_liability",
		],
		order_by="incident_date desc, creation desc",
	)
	emp_ids |= {i.employee for i in incidents if i.employee}

	handovers = frappe.db.sql(
		"""select h.name, h.handover_type, h.posting_date, h.docstatus, h.employee, h.employee_name,
			h.from_employee, i.return_result, i.condition_out, i.condition_in
		from `tabEquipment Handover Item` i
		inner join `tabEquipment Handover` h on h.name = i.parent
		where i.equipment = %s and h.docstatus != 2
		order by h.posting_date desc, h.creation desc""",
		equipment,
		as_dict=True,
	)
	emp_ids |= {h.employee for h in handovers if h.employee} | {h.from_employee for h in handovers if h.from_employee}

	names = {}
	if emp_ids:
		for e in frappe.get_all("Employee", filters={"name": ["in", list(emp_ids)]}, fields=["name", "employee_name"]):
			names[e.name] = e.employee_name or e.name

	periods = custody_history(rows, today, names)
	custody_days = sum(p["days"] for p in periods)
	by_employee = {}
	for p in periods:
		by_employee[p["employee_name"]] = by_employee.get(p["employee_name"], 0) + p["days"]

	first_date = getdate(rows[0].posting_datetime) if rows else (getdate(eq.purchase_date) if eq.purchase_date else getdate(eq.creation))
	age_days = max(date_diff(today, first_date) + 1, 1)
	open_period = next((p for p in periods if not p["to"]), None)

	counts = {}
	for r in rows:
		counts[r.movement_type] = counts.get(r.movement_type, 0) + 1

	kpis = {
		"status": eq.status,
		"condition": eq.condition,
		"custodian": eq.current_custodian,
		"custodian_name": names.get(eq.current_custodian) if eq.current_custodian else None,
		"holding_days": open_period["days"] if open_period else 0,
		"times_issued": counts.get("Issue", 0),
		"movements": len(rows),
		"custody_days": custody_days,
		"age_days": age_days,
		"utilization": round(min(custody_days / age_days * 100, 100), 1) if age_days else 0,
		"warranty_expiry": str(eq.warranty_expiry) if eq.warranty_expiry else None,
		"warranty_days_left": date_diff(eq.warranty_expiry, today) if eq.warranty_expiry else None,
		"purchase_cost": flt(eq.purchase_cost),
		"purchase_date": str(eq.purchase_date) if eq.purchase_date else None,
		"incidents_total": len(incidents),
		"incidents_open": sum(1 for i in incidents if i.status == "Open"),
		"incident_cost": sum(flt(i.estimated_cost) for i in incidents),
		"deductions": sum(flt(i.deduction_amount) for i in incidents if i.employee_liability),
	}

	moves = monthly_moves(rows)
	incident_types = {}
	for i in incidents:
		incident_types[i.incident_type] = incident_types.get(i.incident_type, 0) + 1

	return {
		"equipment": {
			f: eq.get(f)
			for f in (
				"name", "equipment_name", "category", "serial_no", "brand", "model", "site", "company",
				"mac_address", "imei", "supplier", "linked_asset", "accessories_included", "remarks",
			)
		},
		"kpis": kpis,
		"charts": {
			"moves": moves,
			"days_by_employee": {"labels": list(by_employee.keys()), "values": list(by_employee.values())},
			"mix": {"labels": list(counts.keys()), "values": list(counts.values())},
			"incident_types": {"labels": list(incident_types.keys()), "values": list(incident_types.values())},
		},
		"custody": periods,
		"timeline": [
			{
				"when": r.posting_datetime.strftime("%Y-%m-%d %H:%M") if r.posting_datetime else None,
				"movement": r.movement_type,
				"employee": r.employee,
				"employee_name": names.get(r.employee),
				"stock_effect": flt(r.stock_effect),
				"custody_effect": flt(r.custody_effect),
				"reference_doctype": r.reference_doctype,
				"reference_name": r.reference_name,
				"remarks": r.remarks,
			}
			for r in reversed(rows[-200:])
		],
		"handovers": [
			{
				"name": h.name,
				"type": h.handover_type,
				"date": str(h.posting_date),
				"docstatus": h.docstatus,
				"employee": h.employee_name or h.employee,
				"from_employee": names.get(h.from_employee),
				"result": h.return_result,
				"condition": h.condition_in or h.condition_out,
			}
			for h in handovers
		],
		"incidents": [
			{
				"name": i.name,
				"type": i.incident_type,
				"date": str(i.incident_date),
				"status": i.status,
				"resolution": i.resolution,
				"employee": names.get(i.employee),
				"cost": flt(i.estimated_cost),
				"deduction": flt(i.deduction_amount) if i.employee_liability else 0,
			}
			for i in incidents
		],
	}


# ---------------------------------------------------------------------------
# pure helpers (no database access, unit-testable)
# ---------------------------------------------------------------------------
def drop_reversed(rows):
	"""Remove every ledger row that was cancelled together with the reversal that cancelled it."""
	pending = {}
	for idx, r in enumerate(rows):
		if not r.is_reversal:
			key = (r.reference_doctype, r.reference_name, r.reference_row, r.movement_type, r.employee)
			pending.setdefault(key, []).append(idx)

	dropped = set()
	for idx, r in enumerate(rows):
		if r.is_reversal:
			key = (r.reference_doctype, r.reference_name, r.reference_row, r.movement_type, r.employee)
			if pending.get(key):
				dropped.add(pending[key].pop())
				dropped.add(idx)
	return [r for idx, r in enumerate(rows) if idx not in dropped]


def custody_history(rows, today, names):
	"""[{employee, employee_name, from, to (None while still held), days, reference}] from net custody effect."""
	balance, started, periods = {}, {}, []

	def add(emp, start, end, ref_doctype, ref):
		finish = end or today
		periods.append(
			{
				"employee": emp,
				"employee_name": names.get(emp) or emp,
				"from": str(start),
				"to": str(end) if end else None,
				"days": max(date_diff(finish, start) + 1, 1),
				"reference_doctype": ref_doctype,
				"reference": ref,
			}
		)

	for r in rows:
		emp, effect = r.employee, flt(r.custody_effect)
		if not emp or not effect:
			continue
		before = balance.get(emp, 0)
		after = before + effect
		balance[emp] = after
		when = getdate(r.posting_datetime)
		if before <= 0 < after:
			started[emp] = (when, r.reference_doctype, r.reference_name)
		elif before > 0 >= after and emp in started:
			start, ref_doctype, ref = started.pop(emp)
			add(emp, start, when, ref_doctype, ref)

	for emp, (start, ref_doctype, ref) in started.items():
		add(emp, start, None, ref_doctype, ref)

	periods.sort(key=lambda p: p["from"], reverse=True)
	return periods


def monthly_moves(rows):
	"""Stacked-bar data: movements per month, grouped Issue / Return / Transfer / Other."""
	groups = ["Issue", "Return", "Transfer", OTHER]
	counts = {}
	for r in rows:
		if r.movement_type == "Transfer Out":
			continue  # a transfer is one event, counted at the receiving side
		month = getdate(r.posting_datetime).strftime("%Y-%m")
		g = GROUP.get(r.movement_type, OTHER)
		counts.setdefault(month, {k: 0 for k in groups})[g] += 1
	months = sorted(counts)
	return {
		"labels": months,
		"datasets": [{"name": _(g), "values": [counts[m][g] for m in months]} for g in groups],
	}
