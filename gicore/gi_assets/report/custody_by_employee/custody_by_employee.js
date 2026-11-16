frappe.query_reports["Custody by Employee"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "employee", label: __("Employee"), fieldtype: "Link", options: "Employee" },
		{ fieldname: "department", label: __("Department"), fieldtype: "Link", options: "Department" },
		{ fieldname: "category", label: __("Category"), fieldtype: "Link", options: "Equipment Category" },
		{
			fieldname: "employee_status",
			label: __("Employee Status"),
			fieldtype: "Select",
			options: "\nActive\nInactive\nSuspended\nLeft",
		},
	],
};
