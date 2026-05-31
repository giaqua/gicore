frappe.query_reports["Employee Attendance Summary"] = {
	filters: [
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.month_start(),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			onchange: function () {
				const from_date = frappe.query_report.get_filter_value("from_date");
				const to_date   = frappe.query_report.get_filter_value("to_date");
				if (from_date && to_date) {
					const diff = (new Date(to_date) - new Date(from_date)) / (1000 * 60 * 60 * 24);
					if (diff > 29) {
						frappe.msgprint(__("Date range cannot exceed 30 days."));
					}
				}
			},
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_default("Company"),
		},
		{
			fieldname: "department",
			label: __("Department"),
			fieldtype: "Link",
			options: "Department",
		},
		{
			fieldname: "employee",
			label: __("Employee"),
			fieldtype: "Link",
			options: "Employee",
			get_query: function () {
				const company    = frappe.query_report.get_filter_value("company");
				const department = frappe.query_report.get_filter_value("department");
				const filters    = {};
				if (company)    filters["company"]    = company;
				if (department) filters["department"] = department;
				return { filters };
			},
		},
		{
			fieldname: "status_filter",
			label: __("Show Status"),
			fieldtype: "Select",
			options: "\nPresent\nAbsent\nOne Checkin",
		},
		{
			fieldname: "hours_less_than",
			label: __("Hours Less Than"),
			fieldtype: "Float",
			description: __("Show employees whose total hours are less than this value"),
		},
	],

	// ── Custom Print button ──────────────────────────────────────────────────
	onload: function (report) {
		report.page.add_inner_button(__("Print"), function () {
			const filters = frappe.query_report.get_values();

			if (!filters.from_date || !filters.to_date) {
				frappe.msgprint(__("Please set From Date and To Date before printing."));
				return;
			}

			const btn = report.page.add_inner_button(__("Print"));
			btn && btn.prop("disabled", true).text(__("Generating…"));

			frappe.call({
				method: "gicore.gi_hr.report.employee_attendance_summary.employee_attendance_summary.get_print_html",
				// ↑ Replace "your_app.your_app" with your actual app + module path
				args: { filters: filters },
				callback: function (r) {
					btn && btn.prop("disabled", false).text(__("Print"));

					if (r.exc) {
						frappe.msgprint(__("Could not generate print preview. Check the console for details."));
						return;
					}

					const html = r.message;

					// Open in a new popup window and trigger browser print
					const win = window.open("", "_blank", "width=1100,height=750,scrollbars=yes");
					if (!win) {
						frappe.msgprint(__("Please allow popups for this site to use the print feature."));
						return;
					}
					win.document.write(html);
					win.document.close();
					// Give images / fonts a moment to load, then auto-print
					win.onload = function () {
						win.focus();
						win.print();
					};
				},
				error: function () {
					btn && btn.prop("disabled", false).text(__("Print"));
					frappe.msgprint(__("An error occurred while generating the print preview."));
				},
			});
		});
	},

	// ── Cell colour formatter ────────────────────────────────────────────────
	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (column.fieldname && column.fieldname.startsWith("day_")) {
			if (value === "A") {
				value = `<span style="
					color:#fff;background-color:#e74c3c;font-weight:bold;
					padding:0px;border-radius:4px;display:inline-block;
					min-width:28px;text-align:center;">A</span>`;
			} else if (value === "O") {
				value = `<span style="
					color:#fff;background-color:#e67e22;font-weight:bold;
					padding:0px;border-radius:4px;display:inline-block;
					min-width:28px;text-align:center;">O</span>`;
			} else if (value && parseFloat(value) > 0) {
				value = `<span style="
					color:#fff;background-color:#27ae60;font-weight:600;
					padding:0px;border-radius:4px;display:inline-block;
					min-width:36px;text-align:center;">${value}</span>`;
			}
		}

		return value;
	},
};
