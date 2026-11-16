frappe.ui.form.on("Equipment Incident", {
	refresh(frm) {
		if (frm.is_new()) return;

		if (frm.doc.employee_liability && frm.doc.deduction_amount && !frm.doc.additional_salary) {
			frm.add_custom_button(__("Additional Salary (Deduction)"), () => {
				frappe.call({
					method: "gicore.gi_assets.doctype.equipment_incident.equipment_incident.create_additional_salary",
					args: { incident: frm.doc.name },
					freeze: true,
					callback(r) {
						if (r.message) {
							frm.reload_doc();
							frappe.set_route("Form", "Additional Salary", r.message);
						}
					},
				});
			}, __("Create"));
		}
	},
});
