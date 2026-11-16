frappe.ui.form.on("Equipment", {
	setup(frm) {
		frm.set_query("category", () => ({ filters: { tracking_type: "Serialized" } }));
	},

	refresh(frm) {
		if (frm.is_new()) return;
		const d = frm.doc;

		// everything about this unit, in a new browser tab
		frm.add_custom_button(__("360 View"), () => {
			window.open(frappe.urllib.get_full_url("/app/equipment-360/" + encodeURIComponent(d.name)), "_blank");
		}).addClass("btn-primary");

		// ------------------------------------------------------------ Create: pre-filled transactions
		const group = __("Create");
		const add = (label, fn) => frm.add_custom_button(label, fn, group);

		if (d.status === "In Stock") {
			add(__("Issue to Employee"), () => equipment_form_handover(frm, "Issue"));
		}
		if (d.status === "Issued") {
			add(__("Return"), () => equipment_form_handover(frm, "Return"));
			add(__("Transfer to Employee"), () => equipment_form_handover(frm, "Transfer"));
			add(__("Replacement Request"), () => {
				frappe.new_doc("Equipment Request", {
					employee: d.current_custodian,
					request_type: "Replacement",
					category: d.category,
					company: d.company,
				});
			});
		}
		if (d.status === "In Stock" || d.status === "Issued") {
			["Damage", "Loss", "Theft"].forEach((type) =>
				add(__("Report {0}", [__(type)]), () => {
					frappe.new_doc("Equipment Incident", {
						incident_type: type,
						equipment: d.name,
						category: d.category,
						employee: d.current_custodian,
						company: d.company,
					});
				})
			);
		}

		// ------------------------------------------------------------ View
		const view = (label, fn) => frm.add_custom_button(label, fn, __("View"));
		view(__("Ledger"), () => frappe.set_route("List", "Equipment Ledger", { equipment: d.name }));
		view(__("Incidents"), () => frappe.set_route("List", "Equipment Incident", { equipment: d.name }));
		if (d.status === "In Repair") {
			view(__("Open Incident"), () => {
				frappe.db
					.get_value("Equipment Incident", { equipment: d.name, status: "Open" }, "name")
					.then((r) => {
						const name = r && r.message && r.message.name;
						if (name) frappe.set_route("Form", "Equipment Incident", name);
						else frappe.msgprint(__("No open incident for this equipment."));
					});
			});
		}
		if (d.linked_asset) {
			view(__("Linked Asset"), () => frappe.set_route("Form", "Asset", d.linked_asset));
		}

		const colors = { "In Stock": "green", Issued: "blue", "In Repair": "orange", Lost: "red", Scrapped: "gray" };
		frm.page.set_indicator(__(d.status), colors[d.status] || "gray");
	},
});

function equipment_form_handover(frm, kind) {
	const d = frm.doc;
	const opts = { handover_type: kind, company: d.company, site: d.site };
	if (kind === "Return") opts.employee = d.current_custodian;
	if (kind === "Transfer") opts.from_employee = d.current_custodian; // receiver is chosen by the user

	frappe.new_doc("Equipment Handover", opts, (doc) => {
		const row = frappe.model.add_child(doc, "Equipment Handover Item", "items");
		row.category = d.category;
		row.equipment = d.name;
		row.qty = 1;
		if (kind === "Return") row.return_result = "Returned OK";
	});
}
