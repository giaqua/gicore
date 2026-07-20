// Copyright (c) 2026, HM and contributors
// For license information, please see license.txt

frappe.query_reports["Fixed Asset Register with Depreciation Forecast"] = {
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
			fieldname: "asset_category",
			label: __("Asset Category"),
			fieldtype: "Link",
			options: "Asset Category",
		},
		{
			fieldname: "location",
			label: __("Location"),
			fieldtype: "Link",
			options: "Location",
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "Link",
			options: "Cost Center",
			get_query: function () {
				return { filters: { company: frappe.query_report.get_filter_value("company") } };
			},
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
			get_query: function () {
				return { filters: { company: frappe.query_report.get_filter_value("company") } };
			},
		},
		{
			fieldname: "custodian",
			label: __("Custodian"),
			fieldtype: "Link",
			options: "Employee",
		},
		{
			fieldname: "asset",
			label: __("Asset"),
			fieldtype: "Link",
			options: "Asset",
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "include_scrapped_sold",
			label: __("Include Scrapped / Sold Assets"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_forecast",
			label: __("Show Depreciation Forecast"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "forecast_period_type",
			label: __("Forecast Period Type"),
			fieldtype: "Select",
			options: "Monthly\nQuarterly\nYearly",
			default: "Monthly",
			depends_on: "eval:doc.show_forecast",
		},
		{
			fieldname: "forecast_periods",
			label: __("Number of Forecast Periods"),
			fieldtype: "Int",
			default: 12,
			depends_on: "eval:doc.show_forecast",
		},
		{
			fieldname: "forecast_value",
			label: __("Forecast Value"),
			fieldtype: "Select",
			options: "Depreciation Amount\nNet Book Value",
			default: "Depreciation Amount",
			depends_on: "eval:doc.show_forecast",
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname === "net_book_value" && data && flt(data.net_book_value) < 0) {
			value = "<span style='color:#D50000;font-weight:600'>" + value + "</span>";
		}

		if (column.fieldname === "status" && data && data.status) {
			var colors = {
				Submitted: "blue",
				"Partially Depreciated": "orange",
				"Fully Depreciated": "green",
				Scrapped: "red",
				Sold: "grey",
			};
			var color = colors[data.status] || "grey";
			value = "<span class='indicator-pill " + color + "'>" + data.status + "</span>";
		}

		return value;
	},
};
