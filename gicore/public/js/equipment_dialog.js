frappe.provide("gi_equipments");

gi_equipments.STATUS_COLORS = {
	"In Stock": "green", "Issued": "blue", "In Repair": "orange", "Lost": "red", "Scrapped": "gray",
};

// Popup to enter equipment information (professional layout)
gi_equipments.quick_add = function (on_saved) {
	let d = new frappe.ui.Dialog({
		title: __("🖥️ New Equipment"),
		size: "large",
		fields: [
			{ fieldtype: "HTML", fieldname: "hint",
			  options: `<div class="gi-eq-hint">${__("Fill the main details. Brand and Model are lists - type to search or create a new one.")}</div>` },
			{ fieldtype: "Section Break", label: __("Basic Info") },
			{ fieldname: "equipment_name", fieldtype: "Data", label: __("Equipment Name"), reqd: 1 },
			{ fieldname: "category", fieldtype: "Link", options: "Equipment Category", label: __("Category"), reqd: 1,
			  get_query: () => ({ filters: { tracking_type: "Serialized" } }) },
			{ fieldtype: "Column Break" },
			{ fieldname: "brand", fieldtype: "Link", options: "Equipment Brand", label: __("Brand"),
			  onchange: () => { if (d.get_value("model")) { /* keep model only if it matches the brand */
					frappe.db.get_value("Equipment Model", d.get_value("model"), "brand").then(r => {
						if (r.message && r.message.brand !== d.get_value("brand")) d.set_value("model", "");
					}); } } },
			{ fieldname: "model", fieldtype: "Link", options: "Equipment Model", label: __("Model"),
			  get_query: () => ({ filters: d.get_value("brand") ? { brand: d.get_value("brand") } : {} }),
			  onchange: () => {
					let m = d.get_value("model");
					if (!m) return;
					frappe.db.get_value("Equipment Model", m, ["brand", "category"]).then(r => {
						if (!r.message) return;
						if (r.message.brand && d.get_value("brand") !== r.message.brand) d.set_value("brand", r.message.brand);
						if (r.message.category && !d.get_value("category")) d.set_value("category", r.message.category);
					});
			  } },
			{ fieldtype: "Section Break", label: __("Identification & Status") },
			{ fieldname: "serial_no", fieldtype: "Data", label: __("Serial No") },
			{ fieldname: "status", fieldtype: "Select", label: __("Status"), options: "In Stock\nIssued\nIn Repair\nLost\nScrapped", default: "In Stock", read_only: 1 },
			{ fieldtype: "Column Break" },
			{ fieldname: "condition", fieldtype: "Select", label: __("Condition"), options: "New\nGood\nFair\nDamaged", default: "New" },
			{ fieldname: "image", fieldtype: "Attach Image", label: __("Image") },
			{ fieldtype: "Section Break", label: __("Purchase & Warranty") },
			{ fieldname: "purchase_date", fieldtype: "Date", label: __("Purchase Date") },
			{ fieldname: "purchase_cost", fieldtype: "Currency", label: __("Purchase Cost") },
			{ fieldtype: "Column Break" },
			{ fieldname: "warranty_expiry", fieldtype: "Date", label: __("Warranty Expiry") },
			{ fieldname: "supplier", fieldtype: "Link", options: "Supplier", label: __("Supplier") },
			{ fieldtype: "Section Break" },
			{ fieldname: "notes", fieldtype: "Small Text", label: __("Notes") },
		],
		primary_action_label: __("Save Equipment"),
		primary_action: (v) => save(v, false),
	});
	d.$wrapper.addClass("gi-eq-dialog");
	d.add_custom_action(__("Save & Add Another"), () => save(d.get_values(), true));

	function save(values, another) {
		if (!values) return;
		frappe.call({
			method: "frappe.client.insert",
			args: { doc: Object.assign({ doctype: "Equipment" }, values) },
			freeze: true,
			callback: (r) => {
				if (!r.message) return;
				frappe.show_alert({ message: __("Equipment {0} created", [r.message.name]), indicator: "green" });
				if (on_saved) on_saved(r.message);
				if (another) { d.set_value("equipment_name", ""); d.set_value("serial_no", ""); d.set_value("image", ""); }
				else d.hide();
			},
		});
	}
	d.show();
	return d;
};

// Read-only info card for one equipment
gi_equipments.show_info = function (doc) {
	let color = gi_equipments.STATUS_COLORS[doc.status] || "gray";
	let esc = frappe.utils.escape_html;
	let img = doc.image ? `<img src="${encodeURI(doc.image)}">` : "🖥️";
	let row = (l, v) => `<div><span>${l}</span><b>${esc(v || "-")}</b></div>`;
	let d = new frappe.ui.Dialog({
		title: __("Equipment Info"), size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "body", options: `
			<div class="gi-eq-info">
				<div class="gi-eq-img">${img}</div>
				<div style="flex:1">
					<h3>${esc(doc.equipment_name)}</h3>
					<span class="gi-eq-pill">${esc(doc.category || "")}</span>
					<span class="indicator-pill ${color}" style="margin-inline-start:6px">${esc(__(doc.status || ""))}</span>
					<div class="gi-eq-grid">
						${row(__("Brand"), doc.brand)}${row(__("Model"), doc.model)}
						${row(__("Serial No"), doc.serial_no)}${row(__("Condition"), doc.condition)}
						${row(__("Current Holder"), doc.current_custodian)}${row(__("Equipment ID"), doc.name)}
						${row(__("Purchase Date"), doc.purchase_date)}${row(__("Warranty Expiry"), doc.warranty_expiry)}
					</div>
				</div>
			</div>` }],
	});
	d.$wrapper.addClass("gi-eq-dialog");
	d.show();
};