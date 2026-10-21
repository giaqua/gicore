const CC_METHOD = "gicore.gi_hr.doctype.custody_clearance.custody_clearance";
const CC_ACTIVE = ["In Clearance", "On Hold", "Pending Employee Acknowledgement"];

frappe.ui.form.on("Custody Clearance", {
	refresh(frm) {
		frm.trigger("lock_departments");
		frm.trigger("show_progress");
		frm.trigger("add_actions");
	},

	employee(frm) {
		if (!frm.doc.employee) {
			["employee_name", "department", "designation", "company", "user_id"].forEach((f) =>
				frm.set_value(f, "")
			);
		}
	},

	lock_departments(frm) {
		// Departments are editable only in Draft; afterwards use the action buttons
		const locked = !frm.is_new() && frm.doc.overall_status !== "Draft";
		const grid = frm.fields_dict.clearance_departments.grid;
		grid.cannot_add_rows = locked;
		grid.cannot_delete_rows = locked;
		frm.set_df_property("clearance_departments", "read_only", locked ? 1 : 0);
		frm.refresh_field("clearance_departments");
	},

	show_progress(frm) {
		const rows = frm.doc.clearance_departments || [];
		if (frm.is_new() || !rows.length || frm.doc.overall_status === "Draft") return;
		const cleared = rows.filter((r) => r.status === "Cleared").length;
		frm.dashboard.add_progress(
			__("Departments cleared"),
			Math.round((cleared / rows.length) * 100),
			__("{0} of {1} departments cleared", [cleared, rows.length])
		);
	},

	add_actions(frm) {
		if (frm.is_new() || frm.doc.docstatus !== 0) return;
		const status = frm.doc.overall_status;
		const user = frappe.session.user;

		// 1) HR sends the draft to all departments at once
		if (status === "Draft" && frm.perm[0] && frm.perm[0].write) {
			frm.add_custom_button(__("Send for Clearance"), () => {
				frappe.confirm(
					__("Send to all {0} departments now? Departments can only be edited in Draft.", [
						(frm.doc.clearance_departments || []).length,
					]),
					() =>
						(frm.is_dirty() ? frm.save() : Promise.resolve()).then(() =>
							frappe
								.call({ method: `${CC_METHOD}.send_for_clearance`, args: { name: frm.doc.name } })
								.then(() => frm.reload_doc())
						)
				);
			}).addClass("btn-primary");
		}

		// 2) Department approvers (parallel): one button per department they own
		if (CC_ACTIVE.includes(status)) {
			const is_admin = frappe.user.has_role("System Manager");
			(frm.doc.clearance_departments || [])
				.filter((r) => is_admin || r.approver === user || r.alternate_approver === user)
				.forEach((r) => {
					frm.add_custom_button(
						`${r.department} (${__(r.status)})`,
						() => frm.events.department_dialog(frm, r),
						__("Department Action")
					);
				});
		}

		// 3a) HR acknowledges for an employee who has no user account
		if (status === "Pending Employee Acknowledgement" && !frm.doc.user_id) {
			frappe.call({ method: `${CC_METHOD}.can_acknowledge_on_behalf` }).then((r) => {
				if (!r.message) return;
				frm.remove_custom_button(__("Acknowledge on Behalf of Employee"));
				frm.add_custom_button(__("Acknowledge on Behalf of Employee"), () =>
					frm.events.behalf_dialog(frm)
				).addClass("btn-primary");
			});
		}

		// 3b) Employee acknowledgement
		if (status === "Pending Employee Acknowledgement" && frm.doc.user_id && frm.doc.user_id === user) {
			frm.add_custom_button(__("I Acknowledge Clearance"), () => frm.events.acknowledge_dialog(frm)).addClass(
				"btn-primary"
			);
		}
	},

	department_dialog(frm, row) {
		const d = new frappe.ui.Dialog({
			title: __("Custody Clearance: {0}", [row.department]),
			fields: [
				{
					fieldname: "instructions",
					fieldtype: "HTML",
					options: row.instructions
						? `<div class="text-muted small">${frappe.utils.escape_html(row.instructions)}</div>`
						: "",
				},
				{
					fieldname: "status",
					fieldtype: "Select",
					label: __("Decision"),
					options: ["Cleared", "Has Custody"],
					default: row.status === "Has Custody" ? "Has Custody" : "Cleared",
					reqd: 1,
				},
				{
					fieldname: "custody_details",
					fieldtype: "Small Text",
					label: __("Outstanding Custody"),
					depends_on: "eval:doc.status=='Has Custody'",
					mandatory_depends_on: "eval:doc.status=='Has Custody'",
					default: row.custody_details,
				},
				{
					fieldname: "amount_due",
					fieldtype: "Currency",
					label: __("Amount Due"),
					depends_on: "eval:doc.status=='Has Custody'",
					default: row.amount_due,
				},
				{ fieldname: "remarks", fieldtype: "Small Text", label: __("Remarks"), default: row.remarks },
			],
			primary_action_label: __("Submit Decision"),
			primary_action(values) {
				frappe
					.call({
						method: `${CC_METHOD}.update_department_status`,
						args: {
							name: frm.doc.name,
							row_name: row.name,
							status: values.status,
							custody_details: values.custody_details,
							amount_due: values.amount_due || 0,
							remarks: values.remarks,
						},
						freeze: true,
					})
					.then(() => {
						d.hide();
						frm.reload_doc();
					});
			},
		});
		d.show();
	},

	behalf_dialog(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Acknowledge on Behalf of Employee"),
			fields: [
				{
					fieldname: "note",
					fieldtype: "HTML",
					options: `<p>${__(
						"{0} has no user account. Print the clearance, have the employee sign it, then attach the signed copy here.",
						[frappe.utils.escape_html(frm.doc.employee_name)]
					)}</p>`,
				},
				{ fieldname: "signed_copy", fieldtype: "Attach", label: __("Signed Clearance Copy"), reqd: 1 },
				{
					fieldname: "confirm",
					fieldtype: "Check",
					label: __("I confirm the employee signed this clearance"),
					reqd: 1,
				},
			],
			primary_action_label: __("Acknowledge"),
			primary_action(values) {
				if (!values.signed_copy || !values.confirm) return;
				frappe
					.call({
						method: `${CC_METHOD}.acknowledge_on_behalf`,
						args: { name: frm.doc.name, signed_copy: values.signed_copy },
						freeze: true,
					})
					.then(() => {
						d.hide();
						frm.reload_doc();
					});
			},
		});
		d.show();
	},

	acknowledge_dialog(frm) {
		const d = new frappe.ui.Dialog({
			title: __("Employee Acknowledgement"),
			fields: [
				{
					fieldname: "note",
					fieldtype: "HTML",
					options: `<p>${__(
						"I confirm that all departments have cleared my custody and I have no further claims regarding it."
					)}</p>`,
				},
				{ fieldname: "signature", fieldtype: "Signature", label: __("Signature") },
				{ fieldname: "agree", fieldtype: "Check", label: __("I agree"), reqd: 1 },
			],
			primary_action_label: __("Acknowledge"),
			primary_action(values) {
				if (!values.agree) return;
				frappe
					.call({
						method: `${CC_METHOD}.acknowledge`,
						args: { name: frm.doc.name, signature: values.signature },
						freeze: true,
					})
					.then(() => {
						d.hide();
						frm.reload_doc();
					});
			},
		});
		d.show();
	},
});
