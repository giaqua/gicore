// Copyright (c) 2026, HM

frappe.query_reports["Customer Statement"] = {
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
			fieldname: "customer",
			label: __("Customer"),
			fieldtype: "Link",
			options: "Customer",
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.year_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "hide_reconciled",
			label: __("Hide Reconciled Transactions (Open Items Only)"),
			fieldtype: "Check",
			default: 0,
		},
	],

	onload: function (report) {
		report.page.add_inner_button(
			__("Professional Print (IFRS)"),
			() => hm_statements.open_statement_print(report, "Customer"),
			__("HM Statements")
		);
		report.page.add_inner_button(
			__("Download PDF (IFRS)"),
			() => hm_statements.open_statement_print(report, "Customer", true),
			__("HM Statements")
		);
	},
};

// shared helper (also used by Supplier Statement)
window.hm_statements = window.hm_statements || {};
hm_statements.open_statement_print = function (report, party_type, as_pdf) {
	const f = report.get_values();
	const party = party_type === "Customer" ? f.customer : f.supplier;
	if (!party) {
		frappe.msgprint(__("Please select a {0} first", [__(party_type)]));
		return;
	}
	const params = new URLSearchParams({
		party_type: party_type,
		party: party,
		company: f.company,
		from_date: f.from_date,
		to_date: f.to_date,
		as_pdf: as_pdf ? 1 : 0,
		hide_reconciled: f.hide_reconciled ? 1 : 0,
	});
	window.open(
		"/api/method/gicore.gi_accounting.api.statements_api.statement_print?" + params.toString(),
		"_blank"
	);
};
