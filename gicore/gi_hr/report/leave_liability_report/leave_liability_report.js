// Copyright (c) 2026, HM and contributors
// License: MIT

frappe.query_reports["Leave Liability Report"] = {
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
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			get_query: () => {
				const company = frappe.query_report.get_filter_value("company");
				return company ? { filters: { company } } : {};
			},
		},
		{
			fieldname: "leave_type",
			label: __("Leave Type"),
			fieldtype: "Link",
			options: "Leave Type",
		},
		{
			fieldname: "include_lwp",
			label: __("Include Leave Without Pay"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_zero_balance",
			label: __("Show Zero Balances"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "salary_basis",
			label: __("Daily Rate Basis"),
			fieldtype: "Select",
			options: ["Basic Salary (Structure)", "Gross Pay (Latest Salary Slip)"],
			default: "Basic Salary (Structure)",
		},
		{
			fieldname: "days_divisor",
			label: __("Days Divisor"),
			fieldtype: "Int",
			default: 30,
			description: __("Monthly amount is divided by this to get the daily rate (KSA convention: 30)"),
		},
	],

	onload: (report) => {
		report.page.add_inner_button(__("Export Provision JV"), () => {
			frappe.msgprint(__(
				"Use the report totals above as the basis for your month-end leave provision Journal Entry (Dr. Leave Expense, Cr. Leave Liability)."
			));
		});
	},
};