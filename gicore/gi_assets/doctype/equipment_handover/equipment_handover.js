const HANDOVER_METHODS =
	"gicore.gi_assets.doctype.equipment_handover.equipment_handover.";

frappe.ui.form.on("Equipment Handover", {
	setup(frm) {
		frm.set_query("employee", () => ({
			filters: frm.doc.handover_type === "Return" ? {} : { status: "Active" },
		}));

		frm.set_query("equipment_request", () => ({
			filters: {
				docstatus: 1,
				workflow_state: "Approved",
				employee: frm.doc.employee || undefined,
			},
		}));

		// only offer equipment that can actually take part in this movement
		frm.set_query("equipment", "items", (doc, cdt, cdn) => {
			const row = locals[cdt][cdn];
			const filters = {};
			if (row.category) filters.category = row.category;

			if (doc.handover_type === "Issue") {
				filters.status = "In Stock";
			} else {
				filters.status = "Issued";
				const holder = doc.handover_type === "Transfer" ? doc.from_employee : doc.employee;
				if (holder) filters.current_custodian = holder;
			}
			return { filters };
		});
	},

	onload(frm) {
		if (frm.is_new() && !frm.doc.handed_by) {
			frm.set_value("handed_by", frappe.session.user);
		}
	},

	refresh(frm) {
		toggle_item_columns(frm);

		if (frm.doc.docstatus === 0) {
			if (frm.doc.handover_type === "Issue") {
				frm.add_custom_button(
					__("Standard Kit"),
					() => {
						if (!frm.doc.employee) {
							frappe.msgprint(__("Select the employee first."));
							return;
						}
						frappe.call({
							method: HANDOVER_METHODS + "get_kit_items",
							args: { employee: frm.doc.employee },
							callback: (r) => add_rows(frm, r.message),
						});
					},
					__("Get Items From")
				);
			} else {
				frm.add_custom_button(
					__("Current Custody"),
					() => {
						const holder =
							frm.doc.handover_type === "Transfer" ? frm.doc.from_employee : frm.doc.employee;
						if (!holder) {
							frappe.msgprint(
								frm.doc.handover_type === "Transfer"
									? __("Select the From Employee first.")
									: __("Select the employee first.")
							);
							return;
						}
						frappe.call({
							method: HANDOVER_METHODS + "get_employee_custody_items",
							args: { employee: holder },
							callback: (r) => add_rows(frm, r.message),
						});
					},
					__("Get Items From")
				);
			}
		}

		if (frm.doc.docstatus === 1) {
			const colors = { Issue: "blue", Return: "green", Transfer: "orange" };
			frm.page.set_indicator(__(frm.doc.handover_type), colors[frm.doc.handover_type]);
		}
	},

	handover_type(frm) {
		frm.clear_table("items");
		frm.refresh_field("items");
		toggle_item_columns(frm);
	},

	employee(frm) {
		if (frm.doc.employee) {
			frappe.db.get_value("Employee", frm.doc.employee, ["company", "branch"]).then((r) => {
				const v = (r && r.message) || {};
				if (v.company) frm.set_value("company", v.company);
				if (v.branch) frm.set_value("site", v.branch);
			});
		}
	},
});

function toggle_item_columns(frm) {
	const grid = frm.fields_dict.items && frm.fields_dict.items.grid;
	if (!grid) return;
	const is_return = frm.doc.handover_type === "Return";
	grid.update_docfield_property("return_result", "hidden", is_return ? 0 : 1);
	grid.update_docfield_property("condition_in", "hidden", is_return ? 0 : 1);
	frm.refresh_field("items");
}

function add_rows(frm, rows) {
	if (!rows || !rows.length) {
		frappe.msgprint(__("Nothing to add."));
		return;
	}
	// drop empty placeholder rows
	frm.doc.items = (frm.doc.items || []).filter((r) => r.category || r.equipment);
	rows.forEach((d) => frm.add_child("items", d));
	frm.refresh_field("items");
}
