frappe.listview_settings["Custody Clearance"] = {
	add_fields: ["overall_status"],
	get_indicator(doc) {
		const map = {
			Draft: "gray",
			"In Clearance": "orange",
			"On Hold": "red",
			"Pending Employee Acknowledgement": "blue",
			Completed: "green",
			Cancelled: "darkgrey",
		};
		return [__(doc.overall_status), map[doc.overall_status] || "gray", `overall_status,=,${doc.overall_status}`];
	},
};
