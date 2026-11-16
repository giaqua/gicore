frappe.query_reports["Warranty Expiry"] = {
	filters: [
		{ fieldname: "company", label: __("Company"), fieldtype: "Link", options: "Company" },
		{ fieldname: "category", label: __("Category"), fieldtype: "Link", options: "Equipment Category" },
		{ fieldname: "days", label: __("Expiring Within (days)"), fieldtype: "Int", default: 90 },
		{ fieldname: "include_expired", label: __("Include Already Expired"), fieldtype: "Check", default: 0 },
	],
};
