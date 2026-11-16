const EQ360_METHOD = "gicore.gi_assets.page.equipment_360.equipment_360.get_data";

frappe.pages["equipment-360"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Equipment 360"),
		single_column: true,
	});
	wrapper.eq360 = new Equipment360(page, wrapper);
};

frappe.pages["equipment-360"].on_page_show = function (wrapper) {
	const route = frappe.get_route();
	if (wrapper.eq360 && route[1]) {
		wrapper.eq360.set_equipment(decodeURIComponent(route[1]));
	}
};

class Equipment360 {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.current = null;
		this.data = null;

		this.inject_style();
		this.field = page.add_field({
			fieldname: "equipment",
			label: __("Equipment"),
			fieldtype: "Link",
			options: "Equipment",
			change: () => {
				const value = this.field.get_value();
				if (value && value !== this.current) frappe.set_route("equipment-360", value);
			},
		});
		page.set_primary_action(__("Refresh"), () => this.load(), "refresh");

		this.body = $('<div class="eq360"></div>').appendTo(page.main);
		this.show_empty(__("Select an equipment to see everything about it."));
	}

	set_equipment(name) {
		if (name === this.current) return;
		this.current = name;
		this.field.set_value(name);
		this.load();
	}

	load() {
		if (!this.current) return;
		this.show_empty(__("Loading..."));
		frappe
			.call({ method: EQ360_METHOD, args: { equipment: this.current } })
			.then((r) => {
				this.data = r.message;
				this.render();
			})
			.catch(() => this.show_empty(__("Could not load this equipment.")));
	}

	show_empty(text) {
		this.body.html(`<div class="eq-empty text-muted">${frappe.utils.escape_html(text)}</div>`);
	}

	// ------------------------------------------------------------------ render
	render() {
		const d = this.data;
		const e = d.equipment;
		const k = d.kpis;
		this.page.set_title(`${e.equipment_name || e.name}  (${e.name})`);

		this.page.clear_inner_toolbar && this.page.clear_inner_toolbar();
		this.add_buttons();

		this.body.html(`
			${this.header(e, k)}
			<div class="eq-cards">${this.cards(k)}</div>
			<div class="eq-grid">
				${this.chart_box("eq-ch-moves", __("Movements by month"))}
				${this.chart_box("eq-ch-days", __("Days in custody by employee"))}
				${this.chart_box("eq-ch-mix", __("Movement mix"))}
				${this.chart_box("eq-ch-inc", __("Incidents by type"))}
			</div>
			<div class="eq-grid">
				${this.panel(__("Custody history"), this.custody_table(d.custody))}
				${this.panel(__("Unit details"), this.details(e, k))}
			</div>
			${this.panel(__("Handovers"), this.handover_table(d.handovers))}
			${this.panel(__("Incidents"), this.incident_table(d.incidents))}
			${this.panel(__("Movement timeline (latest 200)"), this.timeline_table(d.timeline))}
		`);
		this.draw_charts(d.charts);
	}

	header(e, k) {
		const ind = { "In Stock": "green", Issued: "blue", "In Repair": "orange", Lost: "red", Scrapped: "gray" }[k.status] || "gray";
		const esc = frappe.utils.escape_html;
		return `
			<div class="eq-head">
				<div>
					<div class="eq-title">${esc(e.equipment_name || e.name)}</div>
					<div class="text-muted">
						<a href="${frappe.utils.get_form_link("Equipment", e.name)}">${esc(e.name)}</a>
						&middot; ${esc(e.category || "")}
						${e.serial_no ? "&middot; " + __("Serial") + " " + esc(e.serial_no) : ""}
					</div>
				</div>
				<span class="indicator-pill ${ind}">${esc(__(k.status))}</span>
			</div>`;
	}

	cards(k) {
		const esc = frappe.utils.escape_html;
		const money = (v) => frappe.format(v || 0, { fieldtype: "Currency" });
		const date = (v) => (v ? frappe.datetime.str_to_user(v) : "-");

		let warrantyColor = "";
		let warrantyText = __("No warranty date");
		let warrantySub = "";
		if (k.warranty_days_left !== null && k.warranty_days_left !== undefined) {
			if (k.warranty_days_left < 0) {
				warrantyColor = "red";
				warrantyText = __("Expired");
				warrantySub = __("{0} days ago", [Math.abs(k.warranty_days_left)]);
			} else {
				warrantyColor = k.warranty_days_left <= 30 ? "orange" : "green";
				warrantyText = __("{0} days left", [k.warranty_days_left]);
				warrantySub = date(k.warranty_expiry);
			}
		}

		const card = (label, value, sub, color) => `
			<div class="eq-card ${color || ""}">
				<div class="eq-card-label">${esc(label)}</div>
				<div class="eq-card-value">${value}</div>
				<div class="eq-card-sub text-muted">${sub || "&nbsp;"}</div>
			</div>`;

		return [
			card(__("Status"), esc(__(k.status)), esc(__("Condition")) + ": " + esc(__(k.condition || "-"))),
			card(
				__("Current custodian"),
				k.custodian_name ? esc(k.custodian_name) : "-",
				k.custodian ? __("Holding for {0} days", [k.holding_days]) : __("In store or out of service")
			),
			card(__("Times issued"), k.times_issued, __("{0} movements in total", [k.movements])),
			card(
				__("Days in custody"),
				k.custody_days,
				__("{0}% of {1} days in the system", [k.utilization, k.age_days]),
				k.utilization >= 60 ? "green" : ""
			),
			card(__("Warranty"), esc(warrantyText), esc(warrantySub), warrantyColor),
			card(
				__("Incidents"),
				k.incidents_total,
				__("{0} open", [k.incidents_open]),
				k.incidents_open ? "orange" : ""
			),
			card(__("Incident cost"), money(k.incident_cost), __("Deducted from staff: {0}", [money(k.deductions)])),
			card(__("Purchase cost"), money(k.purchase_cost), k.purchase_date ? date(k.purchase_date) : ""),
		].join("");
	}

	chart_box(id, title) {
		return `<div class="eq-panel"><div class="eq-panel-title">${frappe.utils.escape_html(title)}</div><div id="${id}"></div></div>`;
	}

	panel(title, html) {
		return `<div class="eq-panel"><div class="eq-panel-title">${frappe.utils.escape_html(title)}</div>${html}</div>`;
	}

	table(headers, rows, empty) {
		if (!rows.length) return `<div class="text-muted eq-none">${frappe.utils.escape_html(empty)}</div>`;
		return `<div class="eq-scroll"><table class="table table-bordered eq-table">
			<thead><tr>${headers.map((h) => `<th>${frappe.utils.escape_html(h)}</th>`).join("")}</tr></thead>
			<tbody>${rows.map((r) => `<tr>${r.map((c) => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody>
		</table></div>`;
	}

	link(doctype, name) {
		if (!name) return "";
		return `<a href="${frappe.utils.get_form_link(doctype, name)}">${frappe.utils.escape_html(name)}</a>`;
	}

	custody_table(rows) {
		const date = (v) => (v ? frappe.datetime.str_to_user(v) : `<span class="indicator-pill blue">${__("Now")}</span>`);
		return this.table(
			[__("Employee"), __("From"), __("To"), __("Days"), __("Document")],
			rows.map((p) => [
				frappe.utils.escape_html(p.employee_name),
				frappe.datetime.str_to_user(p.from),
				date(p.to),
				p.days,
				this.link(p.reference_doctype, p.reference),
			]),
			__("This unit has never been issued.")
		);
	}

	details(e, k) {
		const esc = frappe.utils.escape_html;
		const rows = [
			[__("Brand / Model"), [e.brand, e.model].filter(Boolean).join(" ")],
			[__("Site"), e.site],
			[__("Company"), e.company],
			[__("Supplier"), e.supplier],
			[__("MAC address"), e.mac_address],
			[__("IMEI"), e.imei],
			[__("Accessories"), e.accessories_included],
			[__("Linked Asset"), e.linked_asset ? this.link("Asset", e.linked_asset) : ""],
			[__("Remarks"), e.remarks],
		].filter((r) => r[1]);
		if (!rows.length) return `<div class="text-muted eq-none">${__("No extra details recorded.")}</div>`;
		return `<table class="table eq-table"><tbody>${rows
			.map((r) => `<tr><td class="text-muted" style="width:38%">${esc(r[0])}</td><td>${r[0] === __("Linked Asset") ? r[1] : esc(r[1])}</td></tr>`)
			.join("")}</tbody></table>`;
	}

	handover_table(rows) {
		const stateLabel = (s) => (s === 0 ? __("Draft") : __("Submitted"));
		return this.table(
			[__("Document"), __("Type"), __("Date"), __("Employee"), __("Result / Condition"), __("State")],
			rows.map((h) => [
				this.link("Equipment Handover", h.name),
				frappe.utils.escape_html(__(h.type)),
				frappe.datetime.str_to_user(h.date),
				frappe.utils.escape_html(h.employee || "") +
					(h.from_employee ? ` <span class="text-muted">(${__("from")} ${frappe.utils.escape_html(h.from_employee)})</span>` : ""),
				frappe.utils.escape_html([h.result, h.condition].filter(Boolean).join(" / ")),
				stateLabel(h.docstatus),
			]),
			__("No handovers for this unit.")
		);
	}

	incident_table(rows) {
		const money = (v) => (v ? frappe.format(v, { fieldtype: "Currency" }) : "-");
		return this.table(
			[__("Incident"), __("Type"), __("Date"), __("Employee"), __("Status"), __("Resolution"), __("Cost"), __("Deduction")],
			rows.map((i) => [
				this.link("Equipment Incident", i.name),
				frappe.utils.escape_html(__(i.type)),
				frappe.datetime.str_to_user(i.date),
				frappe.utils.escape_html(i.employee || ""),
				frappe.utils.escape_html(__(i.status)),
				frappe.utils.escape_html(__(i.resolution || "")),
				money(i.cost),
				money(i.deduction),
			]),
			__("No incidents. Good.")
		);
	}

	timeline_table(rows) {
		const fmt = (n) => (n > 0 ? "+" + n : n < 0 ? String(n) : "0");
		return this.table(
			[__("When"), __("Movement"), __("Employee"), __("Store"), __("Custody"), __("Document"), __("Remarks")],
			rows.map((t) => [
				frappe.datetime.str_to_user(t.when),
				frappe.utils.escape_html(__(t.movement)),
				frappe.utils.escape_html(t.employee_name || ""),
				fmt(t.stock_effect),
				fmt(t.custody_effect),
				this.link(t.reference_doctype, t.reference_name),
				frappe.utils.escape_html(t.remarks || ""),
			]),
			__("No movements yet.")
		);
	}

	// ------------------------------------------------------------------ charts
	draw_charts(c) {
		const empty = (id, text) => this.body.find("#" + id).html(`<div class="text-muted eq-none">${frappe.utils.escape_html(text)}</div>`);
		const el = (id) => this.body.find("#" + id)[0];

		if (c.moves.labels.length) {
			new frappe.Chart(el("eq-ch-moves"), {
				data: {
					labels: c.moves.labels,
					datasets: c.moves.datasets.map((d) => ({ name: d.name, values: d.values })),
				},
				type: "bar",
				height: 220,
				colors: ["#2490ef", "#29cd42", "#ffa00a", "#98a1ab"],
				barOptions: { stacked: 1, spaceRatio: 0.45 },
				axisOptions: { xIsSeries: 1 },
			});
		} else empty("eq-ch-moves", __("No movements yet."));

		if (c.days_by_employee.labels.length) {
			new frappe.Chart(el("eq-ch-days"), {
				data: { labels: c.days_by_employee.labels, datasets: [{ name: __("Days"), values: c.days_by_employee.values }] },
				type: "bar",
				height: 220,
				colors: ["#2490ef"],
				barOptions: { spaceRatio: 0.5 },
			});
		} else empty("eq-ch-days", __("This unit has never been issued."));

		if (c.mix.labels.length) {
			new frappe.Chart(el("eq-ch-mix"), {
				data: { labels: c.mix.labels.map((l) => __(l)), datasets: [{ values: c.mix.values }] },
				type: "donut",
				height: 220,
			});
		} else empty("eq-ch-mix", __("No movements yet."));

		if (c.incident_types.labels.length) {
			new frappe.Chart(el("eq-ch-inc"), {
				data: { labels: c.incident_types.labels.map((l) => __(l)), datasets: [{ values: c.incident_types.values }] },
				type: "donut",
				height: 220,
				colors: ["#ffa00a", "#e24c4c", "#743ee2"],
			});
		} else empty("eq-ch-inc", __("No incidents. Good."));
	}

	// ------------------------------------------------------------------ actions
	add_buttons() {
		const d = this.data;
		const e = d.equipment;
		const k = d.kpis;
		const group = __("Create");
		const base = { equipment: e.name, category: e.category, company: e.company, site: e.site };

		this.page.add_inner_button(__("Open Equipment"), () => frappe.set_route("Form", "Equipment", e.name));

		const add = (label, fn) => this.page.add_inner_button(label, fn, group);
		if (k.status === "In Stock") add(__("Issue to Employee"), () => eq_new_handover("Issue", base));
		if (k.status === "Issued") {
			add(__("Return"), () => eq_new_handover("Return", base, k.custodian));
			add(__("Transfer to Employee"), () => eq_new_handover("Transfer", base, k.custodian));
			add(__("Replacement Request"), () => eq_new_request(base, k.custodian));
		}
		if (k.status === "In Stock" || k.status === "Issued") {
			["Damage", "Loss", "Theft"].forEach((t) =>
				add(__("Report {0}", [__(t)]), () => eq_new_incident(t, base, k.custodian))
			);
		}
	}

	inject_style() {
		if (document.getElementById("eq360-style")) return;
		const css = `
		.eq360 { padding: 4px 0 24px; }
		.eq-empty { padding: 60px 0; text-align: center; }
		.eq-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; }
		.eq-title { font-size: 20px; font-weight: 600; color: var(--text-color); }
		.eq-cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 12px; margin-bottom: 16px; }
		.eq-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-md, 8px);
			padding: 12px 14px; border-left-width: 4px; }
		.eq-card.green { border-left-color: var(--green-500, #29cd42); }
		.eq-card.orange { border-left-color: var(--orange-500, #ffa00a); }
		.eq-card.red { border-left-color: var(--red-500, #e24c4c); }
		.eq-card-label { font-size: 11px; text-transform: uppercase; letter-spacing: .04em; color: var(--text-muted); }
		.eq-card-value { font-size: 20px; font-weight: 600; color: var(--text-color); margin: 4px 0 2px; word-break: break-word; }
		.eq-card-sub { font-size: 12px; }
		.eq-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(380px, 1fr)); gap: 12px; margin-bottom: 12px; }
		.eq-panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: var(--border-radius-md, 8px);
			padding: 12px 14px; margin-bottom: 12px; min-width: 0; }
		.eq-grid .eq-panel { margin-bottom: 0; }
		.eq-panel-title { font-weight: 600; margin-bottom: 8px; color: var(--text-color); }
		.eq-table { margin: 0; font-size: 12px; }
		.eq-scroll { overflow-x: auto; }
		.eq-none { padding: 18px 0; text-align: center; }
		`;
		$('<style id="eq360-style"></style>').text(css).appendTo(document.head);
	}
}

// -------------------------------------------------------------------- transaction helpers
function eq_new_handover(kind, base, holder) {
	const opts = { handover_type: kind, company: base.company, site: base.site };
	if (kind === "Issue") {
		// receiver is chosen by the user
	} else if (kind === "Return") {
		opts.employee = holder;
	} else {
		opts.from_employee = holder; // Transfer: receiver is chosen by the user
	}
	frappe.new_doc("Equipment Handover", opts, (doc) => {
		const row = frappe.model.add_child(doc, "Equipment Handover Item", "items");
		row.category = base.category;
		row.equipment = base.equipment;
		row.qty = 1;
		if (kind === "Return") row.return_result = "Returned OK";
	});
}

function eq_new_incident(type, base, holder) {
	frappe.new_doc("Equipment Incident", {
		incident_type: type,
		equipment: base.equipment,
		category: base.category,
		employee: holder,
		company: base.company,
	});
}

function eq_new_request(base, holder) {
	frappe.new_doc("Equipment Request", {
		employee: holder,
		request_type: "Replacement",
		category: base.category,
		company: base.company,
	});
}
