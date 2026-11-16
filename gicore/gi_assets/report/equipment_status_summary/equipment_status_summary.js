frappe.query_reports["Equipment Status Summary"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "site", label: __("Site / Branch"), fieldtype: "Link", options: "Branch" },
		{ fieldname: "category", label: __("Category"), fieldtype: "Link", options: "Equipment Category" },
	],
};
