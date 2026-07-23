// Copyright (c) 2026, HM and contributors
// For license information, please see license.txt

frappe.query_reports["Cash Position Dashboard"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1
		},
		{
			fieldname: "as_on_date",
			label: __("As On Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1
		},
		{
			fieldname: "view",
			label: __("View"),
			fieldtype: "Select",
			options: ["Cash Position", "Cash Flow Forecast", "Historical Trend"],
			default: "Cash Position",
			reqd: 1
		},
		{
			fieldname: "account",
			label: __("Bank / Cash Account"),
			fieldtype: "Link",
			options: "Account",
			get_query: function () {
				let company = frappe.query_report.get_filter_value("company");
				return {
					filters: {
						company: company,
						account_type: ["in", ["Bank", "Cash"]],
						is_group: 0
					}
				};
			}
		},
		{
			fieldname: "currency",
			label: __("Currency"),
			fieldtype: "Link",
			options: "Currency"
		},
		{
			fieldname: "from_date",
			label: __("Trend From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -90),
			depends_on: "eval:doc.view=='Historical Trend'"
		},
		{
			fieldname: "granularity",
			label: __("Granularity"),
			fieldtype: "Select",
			options: ["Daily", "Weekly", "Monthly"],
			default: "Daily",
			depends_on: "eval:doc.view=='Historical Trend'"
		}
	],

	onload: function (report) {
		report.page.add_inner_button(__("Refresh"), function () {
			report.refresh();
		});
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		const negative_fields = [
			"balance_company_currency",
			"net_change",
			"closing_balance",
			"b0_7",
			"b8_30",
			"b31_60",
			"b61_90",
			"b90_plus",
			"overdue",
			"total"
		];

		if (data && negative_fields.includes(column.fieldname) && flt(data[column.fieldname]) < 0) {
			value = `<span style="color: #D50000; font-weight: 600;">${value}</span>`;
		}

		if (data && data.bold) {
			value = `<b>${value}</b>`;
		}

		return value;
	}
};