// Copyright (c) 2026, GI Aqua Tech and contributors
// For license information, please see license.txt

frappe.query_reports["PO Payment Status V2"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 0,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 0,
		},
		{
			fieldname: "supplier_group",
			label: __("Supplier Group"),
			fieldtype: "Link",
			options: "Supplier Group",
			on_change: function () {
				// Clear supplier when group changes
				frappe.query_report.set_filter_value("supplier", "");
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
			get_query: function () {
				var group = frappe.query_report.get_filter_value("supplier_group");
				if (group) {
					return { filters: { supplier_group: group } };
				}
				return {};
			},
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "Select",
			options: "\nFully Paid\nNot Paid",
			default: "Not Paid",
		},
		{
			fieldname: "purchase_order",
			label: __("Purchase Order"),
			fieldtype: "Link",
			options: "Purchase Order",
			get_query: function () {
				var supplier = frappe.query_report.get_filter_value("supplier");
				var company  = frappe.query_report.get_filter_value("company");
				var q = { filters: { docstatus: 1 } };
				if (supplier) q.filters.supplier = supplier;
				if (company)  q.filters.company  = company;
				return q;
			},
		},
	],

	// ── Colour-code the Status column ────────────────────────────────────────
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status") {
			if (data && data.status === "Fully Paid") {
				value = `<span style="color: green; font-weight: bold;">${data.status}</span>`;
			} else if (data && data.status === "Not Paid") {
				value = `<span style="color: #c00; font-weight: bold;">${data.status}</span>`;
			}
		}

		// Highlight outstanding amount in red when > 0
		if (column.fieldname === "outstanding_amount" && data && data.outstanding_amount > 0) {
			value = `<span style="color: #c00;">${value}</span>`;
		}

		return value;
	},
};
