import frappe
from frappe.utils import getdate
from frappe.utils.xlsxutils import make_xlsx


EMP_FIELDS = [
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
	"personal_email",
	"date_of_joining",
	"employment_type",
]


def _get_employees(company=None):
	filters = {"status": "Active"}
	if company:
		filters["company"] = company

	employees = frappe.get_all(
		"Employee",
		filters=filters,
		fields=EMP_FIELDS,
		order_by="employee_name asc",
		limit_page_length=0,
	)

	# Orphan guard: reports_to pointing at inactive/missing employee -> root
	active_ids = {e.name for e in employees}
	for e in employees:
		if e.reports_to and e.reports_to not in active_ids:
			e.reports_to = None

	return employees


@frappe.whitelist()
def get_org_data(company=None):
	employees = _get_employees(company)
	departments = {e.department for e in employees if e.department}

	return {
		"employees": employees,
		"stats": {
			"total": len(employees),
			"departments": len(departments),
			"roots": len([e for e in employees if not e.reports_to]),
		},
	}


@frappe.whitelist()
def export_org_excel(company=None):
	"""Download the hierarchy as XLSX (indented by level)."""
	employees = _get_employees(company)

	by_id = {e.name: e for e in employees}
	children = {e.name: [] for e in employees}
	for e in employees:
		if e.reports_to:
			children[e.reports_to].append(e)

	rows = [[
		"Level", "Employee ID", "Employee Name", "Designation", "Department",
		"Branch", "Reports To", "Manager Name", "Email", "Mobile",
		"Joining Date", "Employment Type", "Company",
	]]

	def walk(emp, level):
		manager = by_id.get(emp.reports_to)
		rows.append([
			level,
			emp.name,
			("    " * level) + (emp.employee_name or ""),
			emp.designation or "",
			emp.department or "",
			emp.branch or "",
			emp.reports_to or "",
			manager.employee_name if manager else "",
			emp.company_email or emp.personal_email or "",
			emp.cell_number or "",
			getdate(emp.date_of_joining).strftime("%d-%m-%Y") if emp.date_of_joining else "",
			emp.employment_type or "",
			emp.company or "",
		])
		for child in sorted(children[emp.name], key=lambda c: c.employee_name or ""):
			walk(child, level + 1)

	roots = [e for e in employees if not e.reports_to]
	for r in sorted(roots, key=lambda c: c.employee_name or ""):
		walk(r, 0)

	xlsx = make_xlsx(rows, "Organization Structure")
	frappe.response["filename"] = "organization_structure.xlsx"
	frappe.response["filecontent"] = xlsx.getvalue()
	frappe.response["type"] = "binary"