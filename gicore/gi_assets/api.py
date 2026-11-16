import frappe
from frappe.utils import add_days, nowdate


@frappe.whitelist()
def get_stats():
	"""Counts for the small cards on the Equipment list view."""
	frappe.has_permission("Equipment", "read", throw=True)
	rows = frappe.get_all("Equipment", fields=["status", "count(name) as c"], group_by="status")
	by = {r.status: r.c for r in rows}
	warranty = frappe.db.count(
		"Equipment",
		{"warranty_expiry": ["between", [nowdate(), add_days(nowdate(), 30)]], "status": ["!=", "Retired"]},
	)
	return {
		"total": sum(by.values()),
		"available": by.get("Available", 0),
		"issued": by.get("Issued", 0),
		"in_repair": by.get("In Repair", 0),
		"warranty_soon": warranty,
	}
