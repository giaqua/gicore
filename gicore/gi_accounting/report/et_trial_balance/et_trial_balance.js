// Copyright (c) 2026, HM and contributors
// For license information, please see license.txt
// Adjust the frappe.call `method` path below to match wherever you place
// et_trial_balance.py (assumed here: et_gl app, module "et_gl").

frappe.query_reports["ET Trial Balance"] = {
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
			fieldname: "fiscal_year",
			label: __("Fiscal Year"),
			fieldtype: "Link",
			options: "Fiscal Year",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today()),
			reqd: 1,
			on_change: function (query_report) {
				var fiscal_year = query_report.get_values().fiscal_year;
				if (!fiscal_year) return;
				frappe.model.with_doc("Fiscal Year", fiscal_year, function (r) {
					var fy = frappe.model.get_doc("Fiscal Year", fiscal_year);
					frappe.query_report.set_filter_value({
						from_date: fy.year_start_date,
						to_date: fy.year_end_date,
					});
				});
			},
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[1],
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: erpnext.utils.get_fiscal_year(frappe.datetime.get_today(), true)[2],
		},

		// --- new: classification filters ---
		{
			fieldname: "root_type",
			label: __("Root Type"),
			fieldtype: "Select",
			options: ["", "Asset", "Liability", "Equity", "Income", "Expense"].join("\n"),
		},
		{
			fieldname: "account_type",
			label: __("Account Type"),
			fieldtype: "Select",
			// mirrors the fixed option list on Account.account_type in core ERPNext
			options: [
				"",
				"Accumulated Depreciation",
				"Asset Received But Not Billed",
				"Bank",
				"Cash",
				"Chargeable",
				"Capital Work in Progress",
				"Cost of Goods Sold",
				"Depreciation",
				"Direct Expense",
				"Direct Income",
				"Equity",
				"Expense Account",
				"Expenses Included In Asset Valuation",
				"Expenses Included In Valuation",
				"Fixed Asset",
				"Income Account",
				"Indirect Expense",
				"Indirect Income",
				"Payable",
				"Receivable",
				"Round Off",
				"Stock",
				"Stock Adjustment",
				"Stock Received But Not Billed",
				"Tax",
				"Temporary",
			].join("\n"),
		},
		{
			fieldname: "level",
			label: __("Show Up To Level"),
			fieldtype: "Int",
			description: __("Leave blank to show all levels"),
		},
		{
			fieldname: "only_ledger_accounts",
			label: __("Show Only Ledger Accounts"),
			fieldtype: "Check",
		},

		// --- new: party / transaction filters ---
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Link",
			options: "Party Type",
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "Dynamic Link",
			get_options: function () {
				return frappe.query_report.get_filter_value("party_type");
			},
			depends_on: "eval:doc.party_type",
		},
		{
			fieldname: "voucher_type",
			label: __("Voucher Type"),
			fieldtype: "Select",
			options: [
				"",
				"Sales Invoice",
				"Purchase Invoice",
				"Journal Entry",
				"Payment Entry",
				"Stock Entry",
				"Expense Claim",
				"Asset",
			].join("\n"),
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher No"),
			fieldtype: "Dynamic Link",
			get_options: function () {
				return frappe.query_report.get_filter_value("voucher_type");
			},
			depends_on: "eval:doc.voucher_type",
		},

		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Cost Center", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
			options: "Cost Center",
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "MultiSelectList",
			get_data: function (txt) {
				return frappe.db.get_link_options("Project", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
			options: "Project",
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "presentation_currency",
			label: __("Currency"),
			fieldtype: "Select",
			options: erpnext.get_presentation_currency_list(),
		},
		{
			fieldname: "with_period_closing_entry_for_opening",
			label: __("With Period Closing Entry For Opening Balances"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "with_period_closing_entry_for_current_period",
			label: __("Period Closing Entry For Current Period"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_zero_values",
			label: __("Show zero values"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_unclosed_fy_pl_balances",
			label: __("Show unclosed fiscal year's P&L balances"),
			fieldtype: "Check",
		},
		{
			fieldname: "include_default_book_entries",
			label: __("Include Default FB Entries"),
			fieldtype: "Check",
			default: 1,
		},
		{
			fieldname: "show_net_values",
			label: __("Show net values in opening and closing columns"),
			fieldtype: "Check",
			default: 1,
		},
	],

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		// eye icon in front of leaf (non-group) accounts only — group
		// totals have no single GL entry set to drill into.
		if (column.fieldname == "account" && data && data.account && !data.is_group) {
			value =
				`<span class="et-tb-eye" data-account="${data.account}" ` +
				`title="${__("View Transactions")}" ` +
				`style="cursor:pointer;margin-right:6px;">👁</span>` +
				value;
		}
		return value;
	},

	tree: true,
	name_field: "account",
	parent_field: "parent_account",
	initial_depth: 3,

	onload: function (report) {
		$(report.page.wrapper).on("click", ".et-tb-eye", function () {
			const account = $(this).attr("data-account");
			const f = report.get_values();

			if (!f.company || !f.from_date || !f.to_date) {
				frappe.msgprint(__("Please set Company, From Date and To Date first."));
				return;
			}

			frappe.call({
				method: "gicore.gi_accounting.report.et_trial_balance.et_trial_balance.get_account_transactions",
				args: {
					account: account,
					company: f.company,
					from_date: f.from_date,
					to_date: f.to_date,
					party_type: f.party_type,
					party: f.party,
					cost_center: f.cost_center,
					project: f.project,
					voucher_type: f.voucher_type,
					voucher_no: f.voucher_no,
				},
				freeze: true,
				callback: function (r) {
					console.log(r);
					
					const rows = r.message || [];

					let html = `<div style="max-height:60vh;overflow:auto;">
						<table class="table table-bordered table-sm">
						<thead><tr>
							<th>${__("Date")}</th>
							<th>${__("Voucher Type")}</th>
							<th>${__("Voucher No")}</th>
							<th>${__("Party")}</th>
							<th>${__("Against")}</th>
							<th class="text-right">${__("Debit")}</th>
							<th class="text-right">${__("Credit")}</th>
							<th>${__("Remarks")}</th>
						</tr></thead><tbody>`;

					if (!rows.length) {
						html += `<tr><td colspan="8" class="text-muted text-center">${__(
							"No transactions found"
						)}</td></tr>`;
					}

					rows.forEach(function (d) {
						const route = frappe.utils.get_form_link
							? frappe.utils.get_form_link(d.voucher_type, d.voucher_no)
							: "#";
						html += `<tr>
							<td>${frappe.datetime.str_to_user(d.posting_date)}</td>
							<td>${d.voucher_type || ""}</td>
							<td><a href="${route}" target="_blank">${d.voucher_no || ""}</a></td>
							<td>${d.party || ""}</td>
							<td>${d.against || ""}</td>
							<td class="text-right">${format_currency(d.debit)}</td>
							<td class="text-right">${format_currency(d.credit)}</td>
							<td>${frappe.utils.escape_html(d.remarks || "")}</td>
						</tr>`;
					});

					html += "</tbody></table></div>";

					const dialog = new frappe.ui.Dialog({
						title: __("Transactions") + " — " + account,
						size: "extra-large",
						fields: [{ fieldtype: "HTML", fieldname: "txn_html", options: html }],
					});
					dialog.show();
				},
			});
		});
	},
};

erpnext.utils.add_dimensions("ET Trial Balance", 6);