frappe.ui.form.on("Equipment", {
	setup(frm) {
		frm.set_query("category", () => ({ filters: { tracking_type: "Serialized" } }));
	},

	refresh(frm) {
		if (frm.is_new()) return;

		frm.add_custom_button(__("Ledger"), () => {
			frappe.set_route("List", "Equipment Ledger", { equipment: frm.doc.name });
		}, __("View"));

		if (frm.doc.status === "Issued" || frm.doc.status === "In Stock") {
			frm.add_custom_button(__("Equipment Incident"), () => {
				frappe.new_doc("Equipment Incident", {
					equipment: frm.doc.name,
					category: frm.doc.category,
					employee: frm.doc.current_custodian,
				});
			}, __("Report"));
		}

		if (frm.doc.linked_asset) {
			frm.add_custom_button(__("Linked Asset"), () => {
				frappe.set_route("Form", "Asset", frm.doc.linked_asset);
			}, __("View"));
		}

		const colors = {
			"In Stock": "green",
			Issued: "blue",
			"In Repair": "orange",
			Lost: "red",
			Scrapped: "gray",
		};
		frm.page.set_indicator(__(frm.doc.status), colors[frm.doc.status] || "gray");
	},
});
