// Copyright (c) 2026, GI Aqua Tech and contributors
// For license information, please see license.txt

frappe.query_reports["GI VAT Report"] = {

	// ─── FILTERS ──────────────────────────────────────────────────────────────
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
			default: frappe.datetime.get_today().slice(0, 8) + "01",
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
			fieldname: "report_mode",
			label: __("Report Mode"),
			fieldtype: "Select",
			options: ["Summary", "Detail"],
			default: "Summary",
			reqd: 1,
			on_change: function () {
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "tax_account",
			label: __("VAT Account (optional)"),
			fieldtype: "Link",
			options: "Account",
			get_query: function () {
				return {
					filters: {
						account_type: "Tax",
						company: frappe.query_report.get_filter_value("company"),
					},
				};
			},
		},
	],

	// ─── ROW FORMATTER ────────────────────────────────────────────────────────
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);
		if (!data) return value;

		if (data.is_group) {
			value = `<strong style="color:#1C4E80;font-size:13px;">${value || ""}</strong>`;
		}
		if (data.is_total) {
			value = `<strong style="color:#1A252F;">${value}</strong>`;
		}
		if (data.is_net) {
			const amt = parseFloat(data.vat_amount || 0);
			const col = amt > 0 ? "#C0392B" : "#1E8449";
			value = `<strong style="color:${col};font-size:13px;">${value}</strong>`;
		}
		return value;
	},

	// ─── ON LOAD – register toolbar buttons ───────────────────────────────────
	onload: function (report) {

		// ── Button 1: Print Summary ─────────────────────────────────────────
		report.page.add_button(__("🖨 Print Summary"), function () {
			_trigger_print(report, "Summary");
		});

		// ── Button 2: Print Detail ──────────────────────────────────────────
		report.page.add_button(__("🖨 Print Detail"), function () {
			_trigger_print(report, "Detail");
		});

		// ── Button 3: Export ZATCA CSV ──────────────────────────────────────
		report.page.add_button(__("⬇ Export ZATCA CSV"), function () {
			_export_zatca_csv(report);
		});
	},
};


// ═══════════════════════════════════════════════════════════════════════════
// PRINT FUNCTION  →  calls whitelisted Python method
// ═══════════════════════════════════════════════════════════════════════════

/**
 * _trigger_print(report, mode)
 *
 * Collects current filters, forces the requested mode, calls the
 * whitelisted Python function `print_vat_report`, receives the rendered
 * HTML, then opens it in a new browser tab ready to print.
 *
 * @param {Object} report  - Frappe report object
 * @param {string} mode    - "Summary" | "Detail"
 */
function _trigger_print(report, mode) {
	const filters = report.get_filter_values();

	// Validate minimum required fields
	if (!filters.company || !filters.from_date || !filters.to_date) {
		frappe.msgprint({
			title: __("Missing Filters"),
			message: __("Please set Company, From Date, and To Date before printing."),
			indicator: "orange",
		});
		return;
	}

	// Show a loading indicator on the button
	const btn_label = mode === "Summary" ? __("🖨 Print Summary") : __("🖨 Print Detail");
	frappe.show_alert({ message: __(`Preparing ${mode} print…`), indicator: "blue" });

	frappe.call({
		method: "gicore.gi_accounting.report.gi_vat_report.gi_vat_report.print_vat_report",
		// ↑  Replace "your_app" with your actual app name, e.g.:
		//    "gi_aqua_tech.report.ksa_vat_report.ksa_vat_report.print_vat_report"
		args: {
			filters: JSON.stringify(filters),
			mode: mode,
		},
		freeze: true,
		freeze_message: __(`Building ${mode} VAT Report…`),

		callback: function (r) {
			if (!r || !r.message || !r.message.html) {
				frappe.msgprint({
					title: __("Print Error"),
					message: __("Could not generate the print format. Check the error log."),
					indicator: "red",
				});
				return;
			}

			const result   = r.message;
			const html     = result.html;
			const filename = result.filename || `KSA_VAT_Report_${mode}.html`;

			// Open rendered HTML in a new tab with #autoprint hash
			// The embedded JS in the HTML auto-triggers window.print()
			const blob = new Blob([html], { type: "text/html;charset=utf-8;" });
			const url  = URL.createObjectURL(blob);

			// Open new window, append autoprint hash
			const win = window.open(url + "#autoprint", "_blank");

			if (!win) {
				// Pop-up blocked – fallback: inject into a dialog
				frappe.msgprint({
					title: __("Pop-up Blocked"),
					message: __("Your browser blocked the print window. Please allow pop-ups for this site and try again, or use the download link below.<br><br>") +
						`<a href="${url}" download="${filename}" class="btn btn-primary btn-sm">⬇ Download HTML</a>`,
					indicator: "orange",
				});
				return;
			}

			frappe.show_alert({
				message: __(`${mode} VAT Report opened in new tab`),
				indicator: "green",
			});

			// Revoke blob URL after a delay to free memory
			setTimeout(() => URL.revokeObjectURL(url), 60000);
		},

		error: function (r) {
			frappe.msgprint({
				title: __("Server Error"),
				message: __("Failed to generate print format. Check ERPNext error log."),
				indicator: "red",
			});
		},
	});
}


// ═══════════════════════════════════════════════════════════════════════════
// ZATCA CSV EXPORT
// ═══════════════════════════════════════════════════════════════════════════

function _export_zatca_csv(report) {
	const data    = report.data || [];
	const filters = report.get_filter_values();
	const mode    = filters.report_mode || "Summary";

	if (!data.length) {
		frappe.msgprint(__("No data to export. Run the report first."));
		return;
	}

	const company = filters.company || "";
	let csvRows = [];
	csvRows.push(`"GI VAT Report – ${mode}"`);
	csvRows.push(`"Company: ${company}"`);
	csvRows.push(`"Period: ${filters.from_date || ""} to ${filters.to_date || ""}"`);
	csvRows.push(`"Generated: ${frappe.datetime.now_datetime()}"`);
	csvRows.push("");

	if (mode === "Summary") {
		csvRows.push('"VAT Category","Description (EN)","Description (AR)","Taxable Amount (SAR)","VAT Amount (SAR)"');
		data.forEach(function (row) {
			if (!row.vat_category) return;
			csvRows.push([
				`"${_esc(row.vat_category)}"`,
				`"${_esc(row.description_en)}"`,
				`"${_esc(row.description_ar)}"`,
				row.taxable_amount != null ? _fltc(row.taxable_amount) : "",
				row.vat_amount     != null ? _fltc(row.vat_amount)     : "",
			].join(","));
		});
	} else {
		csvRows.push('"Date","Type","Document No.","Party","VAT No.","Category","Taxable (SAR)","Rate %","VAT (SAR)","Total (SAR)","Currency"');
		data.forEach(function (row) {
			if (!row.name && !row.is_total && !row.is_net && !row.is_group) return;
			if (row.is_group) {
				csvRows.push(`"${_esc(row.doctype_label)}"`);
				return;
			}
			csvRows.push([
				`"${row.posting_date || ""}"`,
				`"${_esc(row.doctype_label)}"`,
				`"${_esc(row.name)}"`,
				`"${_esc(row.party)}"`,
				`"${_esc(row.tax_id)}"`,
				`"${_esc(row.vat_category)}"`,
				row.taxable_amount != null ? _fltc(row.taxable_amount) : "",
				row.vat_rate       != null ? _fltc(row.vat_rate)       : "",
				row.vat_amount     != null ? _fltc(row.vat_amount)     : "",
				row.total          != null ? _fltc(row.total)          : "",
				`"${row.currency || ""}"`,
			].join(","));
		});
	}

	const csv  = csvRows.join("\n");
	const blob = new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8;" });
	const url  = URL.createObjectURL(blob);
	const a    = document.createElement("a");
	a.href     = url;
	a.download = `KSA_VAT_Report_${mode}_${filters.from_date || ""}__${filters.to_date || ""}.csv`;
	document.body.appendChild(a);
	a.click();
	document.body.removeChild(a);
	URL.revokeObjectURL(url);

	frappe.show_alert({ message: __("ZATCA CSV exported"), indicator: "green" });
}

// ── CSV helpers ───────────────────────────────────────────────────────────
function _esc(v)  { return (v || "").toString().replace(/"/g, '""'); }
function _fltc(v) { return parseFloat(v || 0).toFixed(2); }
