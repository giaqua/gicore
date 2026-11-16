frappe.ui.form.on("Equipment Stock Entry", {
	setup(frm) {
		frm.set_query("category", () => ({ filters: { tracking_type: "Quantity" } }));
	},
});
