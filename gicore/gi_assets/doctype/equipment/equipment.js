frappe.ui.form.on("Equipment", {
	setup(frm) {
		frm.set_query("model", () => ({ filters: frm.doc.brand ? { brand: frm.doc.brand } : {} }));
	},
	refresh(frm) {
		if (frm.is_new()) return;
		frm.add_custom_button(__("Info"), () => gi_equipments.show_info(frm.doc));
		frm.add_custom_button(__("New Equipment"), () => gi_equipments.quick_add((doc) => frappe.set_route("Form", "Equipment", doc.name)));
	},
	model(frm) {
		if (!frm.doc.model) return;
		frappe.db.get_value("Equipment Model", frm.doc.model, ["brand", "category"]).then((r) => {
			if (!r.message) return;
			if (r.message.brand) frm.set_value("brand", r.message.brand);
			if (r.message.category && !frm.doc.category) frm.set_value("category", r.message.category);
		});
	},
	brand(frm) {
		if (!frm.doc.model || !frm.doc.brand) return;
		frappe.db.get_value("Equipment Model", frm.doc.model, "brand").then((r) => {
			if (r.message && r.message.brand !== frm.doc.brand) frm.set_value("model", "");
		});
	},
});
