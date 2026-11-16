frappe.query_reports["Left Employees With Custody"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "category", label: __("Category"), fieldtype: "Link", options: "Equipment Category" },
	],
};
