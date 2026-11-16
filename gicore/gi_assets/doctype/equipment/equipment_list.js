frappe.listview_settings["Equipment"] = {
	add_fields: ["status", "brand", "model", "current_holder"],
	get_indicator(doc) {
		let c = gi_equipments.STATUS_COLORS[doc.status] || "gray";
		return [__(doc.status), c, "status,=," + doc.status];
	},
	onload(listview) {
		listview.page.set_primary_action(__("New Equipment"), () => gi_equipments.quick_add(() => listview.refresh()), "add");
	},
	refresh(listview) {
		if (!listview.$gi_cards) {
			listview.$gi_cards = $('<div class="gi-eq-cards"></div>').insertBefore(listview.$result);
		}
		frappe.call("gicore.gi_assets.api.get_stats").then((r) => {
			let s = r.message || {};
			let cards = [
				["gi-eq-c-total", "🗂️", s.total, __("Total"), null],
				["gi-eq-c-avail", "✅", s.available, __("Available"), "Available"],
				["gi-eq-c-issued", "👤", s.issued, __("Issued"), "Issued"],
				["gi-eq-c-repair", "🛠️", s.in_repair, __("In Repair"), "In Repair"],
				["gi-eq-c-warr", "⏳", s.warranty_soon, __("Warranty ≤ 30d"), null],
			];
			listview.$gi_cards.html(cards.map((c) => `
				<div class="gi-eq-card ${c[0]}" data-status="${c[4] || ""}">
					<div class="gi-eq-ico">${c[1]}</div>
					<div><div class="gi-eq-num">${c[2] || 0}</div><div class="gi-eq-lbl">${c[3]}</div></div>
				</div>`).join(""));
			listview.$gi_cards.find(".gi-eq-card").on("click", function () {
				let st = $(this).attr("data-status");
				listview.filter_area.clear();
				if (st) listview.filter_area.add([["Equipment", "status", "=", st]]);
			});
		});
	},
};
