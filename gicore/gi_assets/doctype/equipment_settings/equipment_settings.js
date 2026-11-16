const DEMO_METHODS = "gicore.gi_assets.demo_data.";

frappe.ui.form.on("Equipment Settings", {
	create_demo_data(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first."));
			return;
		}
		frappe.confirm(
			__(
				"Create sample equipment, stock, handovers, an incident and a request using two existing Active employees? " +
					"You can remove everything again with Delete Demo Data."
			),
			() => {
				frappe.call({
					method: DEMO_METHODS + "create_demo_data",
					freeze: true,
					freeze_message: __("Creating demo data..."),
					callback(r) {
						if (!r.message) return;
						const counts = Object.entries(r.message.counts || {})
							.map(([k, v]) => `${v} x ${__(k)}`)
							.join("<br>");
						frappe.msgprint({
							title: __("Demo data created"),
							indicator: "green",
							message:
								__("Used employees: {0}", [(r.message.employees || []).join(", ")]) +
								"<br><br>" +
								counts,
						});
						frm.reload_doc();
					},
				});
			}
		);
	},

	delete_demo_data(frm) {
		if (frm.is_dirty()) {
			frappe.msgprint(__("Save the settings first."));
			return;
		}
		frappe.confirm(
			__(
				"Delete all demo data? This removes the Demo categories, units, stock entries, handovers, incidents, requests, " +
					"the demo kit and their ledger rows. Your own data is not touched."
			),
			() => {
				frappe.call({
					method: DEMO_METHODS + "delete_demo_data",
					freeze: true,
					freeze_message: __("Deleting demo data..."),
					callback(r) {
						if (!r.message) return;
						const counts = Object.entries(r.message.counts || {})
							.map(([k, v]) => `${v} x ${__(k)}`)
							.join("<br>");
						frappe.msgprint({ title: __("Demo data deleted"), indicator: "green", message: counts });
						frm.reload_doc();
					},
				});
			}
		);
	},
});
