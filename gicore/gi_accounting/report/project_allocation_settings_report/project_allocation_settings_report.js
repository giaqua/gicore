frappe.query_reports["Project Allocation Settings Report"] = {
	filters: [
		{
			fieldname: "view_type",
			label: __("View"),
			fieldtype: "Select",
			options: ["Detail", "Summary (Lump Sum)"],
			default: "Detail",
		},
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
		},
		{
			fieldname: "source_project",
			label: __("Source Project"),
			fieldtype: "Link",
			options: "Project",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			description: __("Shows Settings records overlapping this range \u2014 does not override their own dates"),
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			description: __("Shows Settings records overlapping this range \u2014 does not override their own dates"),
		},
	],

	onload(report) {
		report.page.add_inner_button(__("Post Journal Entry"), () => {
			const filters = report.get_values();

			if (!filters.source_project) {
				frappe.msgprint(__("Select a Source Project filter first, then click Post."));
				return;
			}

			frappe.db.get_doc("HM Project Allocation Settings", filters.source_project).then((setting) => {
				frappe.confirm(
					__("Post a Journal Entry allocating {0}'s cost for {1} to {2}?", [
						filters.source_project, setting.start_date, setting.end_date,
					]),
					() => {
						frappe.call({
							method: "gicore.gi_accounting.report.project_allocation_settings_report.project_allocation_settings_report.post_allocation_journal_entry",
							args: {
								source_project: filters.source_project,
							},
							callback: (r) => {
								if (r.message) {
									frappe.msgprint(__("Journal Entry {0} posted.", [r.message]));
									report.refresh();
								}
							},
						});
					}
				);
			});
		});
	},
};