import frappe


@frappe.whitelist()
def get_org_data(company=None):
	"""Return active employees + summary stats for the org chart.

	Flat list; the client builds the tree from reports_to.
	"""
	filters = {"status": "Active"}
	if company:
		filters["company"] = company

	employees = frappe.get_all(
		"Employee",
		filters=filters,
		fields=[
			"name",
			"employee_name",
			"designation",
			"department",
			"branch",
			"company",
			"image",
			"reports_to",
			"cell_number",
			"company_email",
			"user_id",
		],
		order_by="employee_name asc",
		limit_page_length=0,
	)

	# Orphan guard: if reports_to points to an inactive/missing employee,
	# treat the node as a root instead of dropping it silently.
	active_ids = {e.name for e in employees}
	for e in employees:
		if e.reports_to and e.reports_to not in active_ids:
			e.reports_to = None

	departments = {e.department for e in employees if e.department}

	return {
		"employees": employees,
		"stats": {
			"total": len(employees),
			"departments": len(departments),
			"roots": len([e for e in employees if not e.reports_to]),
		},
		"companies": frappe.get_all("Company", pluck="name", order_by="name"),
	}