frappe.listview_settings["Equipment"] = {
	add_fields: ["status"],
	get_indicator(doc) {
		const colors = {
			"In Stock": "green",
			Issued: "blue",
			"In Repair": "orange",
			Lost: "red",
			Scrapped: "gray",
		};
		return [__(doc.status), colors[doc.status] || "gray", "status,=," + doc.status];
	},
};
