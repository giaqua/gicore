frappe.ui.form.on("Equipment Request", {
	onload(frm) {
		if (frm.is_new() && !frm.doc.employee) {
			frappe.db
				.get_value("Employee", { user_id: frappe.session.user }, "name")
				.then((r) => {
					if (r && r.message && r.message.name) {
						frm.set_value("employee", r.message.name);
					}
				});
		}
	},

	refresh(frm) {
		if (frm.doc.docstatus === 1 && frm.doc.workflow_state === "Approved") {
			frm.add_custom_button(__("Equipment Handover (Issue)"), () => {
				frappe.new_doc(
					"Equipment Handover",
					{
						handover_type: "Issue",
						employee: frm.doc.employee,
						company: frm.doc.company,
						equipment_request: frm.doc.name,
					},
					(doc) => {
						const row = frappe.model.add_child(doc, "Equipment Handover Item", "items");
						row.category = frm.doc.category;
						row.qty = 1;
					}
				);
			}, __("Create"));
		}
	},
});
