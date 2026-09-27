frappe.ui.form.on("Project Overhead Allocation", {
	refresh(frm) {
		if (frm.doc.docstatus === 0) {
			frm.add_custom_button(__("Fetch & Allocate"), () => {
				if (!frm.doc.from_date || !frm.doc.to_date) {
					frappe.msgprint(__("Please set From Date and To Date"));
					return;
				}
				frm.call({
					method: "fetch_and_allocate",
					doc: frm.doc,
					freeze: true,
					freeze_message: __("Fetching accounts and treated water..."),
				}).then(() => {
					frm.dirty();
					frm.refresh_fields();
					frappe.show_alert({ message: __("Allocation updated"), indicator: "green" });
				});
			}).addClass("btn-primary");
		}
	},
});