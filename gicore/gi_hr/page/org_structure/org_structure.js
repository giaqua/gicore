frappe.pages["org-structure"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Organization Structure"),
		single_column: true,
	});
	new OrgStructure(page);
};

const HM_BLUE = "#010BCE";
const HM_RED = "#D50000";
const DEPT_PALETTE = [
	"#010BCE", "#0E7C66", "#B4530A", "#7C3AED", "#BE185D",
	"#0369A1", "#4D7C0F", "#A16207", "#9F1239", "#334155",
];

// adjust dotted path to your app/module
const API = "gicore.gi_hr.page.org_structure.org_structure";

class OrgStructure {
	constructor(page) {
		this.page = page;
		this.company = frappe.defaults.get_user_default("Company");
		this.collapsed = new Set();
		this.zoom = 1;
		this.layout = "vertical"; // "vertical" | "tree"

		this.inject_css();
		this.make_toolbar();
		this.make_body();
		this.make_popover();
		this.load();
	}

	// ================================================================ toolbar
	make_toolbar() {
		this.company_field = this.page.add_field({
			fieldname: "company", label: __("Company"),
			fieldtype: "Link", options: "Company", default: this.company,
			change: () => { this.company = this.company_field.get_value(); this.load(); },
		});

		this.layout_field = this.page.add_field({
			fieldname: "layout", label: __("Layout"),
			fieldtype: "Select", options: ["Vertical", "Tree"], default: "Vertical",
			change: () => {
				this.layout = this.layout_field.get_value() === "Tree" ? "tree" : "vertical";
				this.render();
				if (this.layout === "tree") setTimeout(() => this.fit_to_screen(), 60);
			},
		});

		this.search_field = this.page.add_field({
			fieldname: "search", label: __("Search"),
			fieldtype: "Data",
			change: () => this.apply_search(this.search_field.get_value()),
		});

		this.page.set_primary_action(__("Export Excel"), () => this.export_excel(), "file");
		this.page.add_menu_item(__("Print"), () => this.print_chart());
		this.page.add_menu_item(__("Expand All"), () => { this.collapsed.clear(); this.render(); });
		this.page.add_menu_item(__("Collapse to Level 2"), () => this.collapse_to_level(2));
	}

	// ================================================================ layout
	make_body() {
		this.$body = $(`
			<div class="hm-org">
				<div class="hm-org-bar">
					<div class="hm-org-stats"></div>
					<div class="hm-org-legend"></div>
				</div>
				<div class="hm-org-viewport">
					<div class="hm-org-canvas"><div class="hm-org-tree"></div></div>
					<div class="hm-zoom-ctl">
						<button data-z="in" title="${__("Zoom in")}">+</button>
						<button data-z="out" title="${__("Zoom out")}">&minus;</button>
						<button data-z="fit" title="${__("Fit to screen")}">${__("Fit")}</button>
						<button data-z="reset" title="100%">1:1</button>
						<span class="hm-zoom-pct">100%</span>
					</div>
				</div>
			</div>
		`).appendTo(this.page.main);

		this.$viewport = this.$body.find(".hm-org-viewport");
		this.$canvas = this.$body.find(".hm-org-canvas");
		this.$tree = this.$body.find(".hm-org-tree");

		this.$body.find(".hm-zoom-ctl button").on("click", (e) => {
			const z = $(e.currentTarget).data("z");
			if (z === "in") this.set_zoom(this.zoom + 0.1);
			else if (z === "out") this.set_zoom(this.zoom - 0.1);
			else if (z === "reset") this.set_zoom(1);
			else this.fit_to_screen();
		});

		// drag-to-pan (tree mode only)
		let dragging = false, sx, sy, sl, st;
		this.$viewport.on("mousedown", (e) => {
			if (this.layout !== "tree") return;
			if ($(e.target).closest(".hm-card, .hm-zoom-ctl").length) return;
			dragging = true; sx = e.pageX; sy = e.pageY;
			sl = this.$viewport.scrollLeft(); st = this.$viewport.scrollTop();
			this.$viewport.addClass("hm-grabbing");
		});
		$(document).on("mousemove.hmorg", (e) => {
			if (!dragging) return;
			this.$viewport.scrollLeft(sl - (e.pageX - sx));
			this.$viewport.scrollTop(st - (e.pageY - sy));
		}).on("mouseup.hmorg", () => {
			dragging = false;
			this.$viewport.removeClass("hm-grabbing");
		});

		this.$viewport.on("wheel", (e) => {
			if (this.layout !== "tree" || !e.ctrlKey) return;
			e.preventDefault();
			this.set_zoom(this.zoom + (e.originalEvent.deltaY < 0 ? 0.08 : -0.08));
		});
	}

	set_zoom(z) {
		if (this.layout !== "tree") return;
		this.zoom = Math.min(2, Math.max(0.25, z));
		this.$tree.css("transform", `scale(${this.zoom})`);
		this.$body.find(".hm-zoom-pct").text(Math.round(this.zoom * 100) + "%");
		this.$canvas.css({
			width: this.$tree[0].scrollWidth * this.zoom + 80,
			height: this.$tree[0].scrollHeight * this.zoom + 80,
		});
	}

	fit_to_screen() {
		if (this.layout !== "tree") return;
		const tw = this.$tree[0].scrollWidth, vw = this.$viewport.width() - 40;
		const th = this.$tree[0].scrollHeight, vh = this.$viewport.height() - 40;
		if (tw && th) this.set_zoom(Math.min(vw / tw, vh / th, 1));
		this.$viewport.scrollLeft(0).scrollTop(0);
	}

	// ================================================================ data
	load() {
		frappe.call({
			method: `${API}.get_org_data`,
			args: { company: this.company },
			freeze: true,
			callback: (r) => {
				this.data = r.message || { employees: [], stats: {} };
				this.index();
				this.render();
				if (this.layout === "tree") setTimeout(() => this.fit_to_screen(), 60);
			},
		});
	}

	index() {
		this.by_id = {}; this.children_map = {}; this.dept_color = {};
		let ci = 0;
		(this.data.employees || []).forEach((e) => {
			this.by_id[e.name] = e;
			this.children_map[e.name] = [];
			if (e.department && !(e.department in this.dept_color)) {
				this.dept_color[e.department] = DEPT_PALETTE[ci++ % DEPT_PALETTE.length];
			}
		});
		(this.data.employees || []).forEach((e) => {
			if (e.reports_to) this.children_map[e.reports_to].push(e);
		});
		this.roots = (this.data.employees || []).filter((e) => !e.reports_to);
	}

	total_reports(id) {
		let n = 0;
		const walk = (x) => (this.children_map[x] || []).forEach((c) => { n++; walk(c.name); });
		walk(id);
		return n;
	}

	collapse_to_level(max) {
		this.collapsed.clear();
		const walk = (emp, lvl) => {
			if (lvl >= max && this.children_map[emp.name].length) this.collapsed.add(emp.name);
			this.children_map[emp.name].forEach((c) => walk(c, lvl + 1));
		};
		this.roots.forEach((r) => walk(r, 1));
		this.render();
	}

	// ================================================================ render
	render() {
		const s = this.data.stats || {};
		this.$body.find(".hm-org-stats").html(`
			<span><b>${s.total || 0}</b> ${__("Employees")}</span>
			<span><b>${s.departments || 0}</b> ${__("Departments")}</span>
		`);
		this.$body.find(".hm-org-legend").html(
			Object.entries(this.dept_color)
				.map(([d, c]) => `<span class="hm-lg"><i style="background:${c}"></i>${frappe.utils.escape_html(d.split(" - ")[0])}</span>`)
				.join("")
		);

		const is_v = this.layout === "vertical";
		this.$viewport.toggleClass("hm-mode-vertical", is_v).toggleClass("hm-mode-tree", !is_v);
		this.$body.find(".hm-zoom-ctl").toggle(!is_v);
		this.$tree.css("transform", is_v ? "none" : `scale(${this.zoom})`);
		if (is_v) this.$canvas.css({ width: "", height: "" });

		this.$tree.empty();
		if (!this.roots.length) {
			this.$tree.html(`<div class="hm-org-empty">${__("No active employees found.")}</div>`);
			return;
		}

		if (is_v) {
			const $wrap = $('<div class="hm-v-wrap"></div>').appendTo(this.$tree);
			this.roots.forEach((r) => this.render_v_node(r, $wrap, 0));
		} else {
			const $rootUl = $('<ul class="hm-lvl hm-root"></ul>').appendTo(this.$tree);
			this.roots.forEach((r) => this.render_t_node(r, $rootUl));
			this.set_zoom(this.zoom);
		}
	}

	card_html(emp, kids, is_collapsed, vertical) {
		const color = this.dept_color[emp.department] || HM_BLUE;
		const avatar = emp.image
			? `<img src="${emp.image}" loading="lazy" alt="">`
			: `<span class="hm-initials" style="background:${color}">${frappe.get_abbr(emp.employee_name)}</span>`;

		const toggle = kids.length
			? `<button class="hm-toggle ${vertical ? "hm-toggle-v" : ""}">
				${is_collapsed ? "+" + this.total_reports(emp.name) : "&minus;"}
			   </button>`
			: (vertical ? `<span class="hm-toggle-spacer"></span>` : "");

		const extra = vertical
			? `<div class="hm-tags">
				${emp.department ? `<span class="hm-chip" style="background:${color}1a;color:${color}">${frappe.utils.escape_html(emp.department.split(" - ")[0])}</span>` : ""}
				${kids.length ? `<span class="hm-count">${kids.length} ${__("direct")} · ${this.total_reports(emp.name)} ${__("team")}</span>` : ""}
			   </div>`
			: "";

		return `
			<div class="hm-card ${vertical ? "hm-card-v" : ""}" data-emp="${emp.name}" style="--dept:${color}">
				${vertical ? toggle : ""}
				<div class="hm-avatar">${avatar}</div>
				<div class="hm-meta">
					<div class="hm-name">${frappe.utils.escape_html(emp.employee_name)}</div>
					<div class="hm-desig">${frappe.utils.escape_html(emp.designation || "")}</div>
				</div>
				${extra}
				${vertical ? "" : toggle}
			</div>`;
	}

	bind_card(emp, $card, is_collapsed) {
		$card.on("click", (ev) => {
			if ($(ev.target).closest(".hm-toggle").length) return;
			frappe.set_route("Form", "Employee", emp.name);
		});
		$card.on("mouseenter", () => this.show_popover(emp, $card));
		$card.on("mouseleave", () => this.hide_popover());
		$card.find(".hm-toggle").on("click", (ev) => {
			ev.stopPropagation();
			is_collapsed ? this.collapsed.delete(emp.name) : this.collapsed.add(emp.name);
			this.render();
		});
	}

	// ---- vertical (indented) layout
	render_v_node(emp, $parent, level) {
		const kids = this.children_map[emp.name] || [];
		const is_collapsed = this.collapsed.has(emp.name);

		const $node = $('<div class="hm-v-node"></div>').appendTo($parent);
		const $row = $('<div class="hm-v-row"></div>').appendTo($node);
		const $card = $(this.card_html(emp, kids, is_collapsed, true)).appendTo($row);
		this.bind_card(emp, $card, is_collapsed);

		if (kids.length && !is_collapsed) {
			const $kids = $('<div class="hm-v-kids"></div>').appendTo($node);
			kids.forEach((k) => this.render_v_node(k, $kids, level + 1));
		}
	}

	// ---- classic top-down tree layout
	render_t_node(emp, $parentUl) {
		const kids = this.children_map[emp.name] || [];
		const is_collapsed = this.collapsed.has(emp.name);
		const $li = $("<li></li>").appendTo($parentUl);
		const $card = $(this.card_html(emp, kids, is_collapsed, false)).appendTo($li);
		this.bind_card(emp, $card, is_collapsed);

		if (kids.length && !is_collapsed) {
			const $ul = $('<ul class="hm-lvl"></ul>').appendTo($li);
			kids.forEach((k) => this.render_t_node(k, $ul));
		}
	}

	// ================================================================ popover
	make_popover() {
		this.$pop = $('<div class="hm-pop" style="display:none"></div>').appendTo("body");
		this.$pop.on("mouseenter", () => clearTimeout(this._pop_t));
		this.$pop.on("mouseleave", () => this.hide_popover());
	}

	show_popover(emp, $card) {
		clearTimeout(this._pop_t);
		const color = this.dept_color[emp.department] || HM_BLUE;
		const direct = (this.children_map[emp.name] || []).length;
		const total = this.total_reports(emp.name);
		const mgr = this.by_id[emp.reports_to];
		const img = emp.image
			? `<img src="${emp.image}" alt="">`
			: `<span class="hm-pop-initials" style="background:${color}">${frappe.get_abbr(emp.employee_name)}</span>`;

		const row = (icon, val) =>
			val ? `<div class="hm-pop-row"><span>${icon}</span>${frappe.utils.escape_html(String(val))}</div>` : "";

		this.$pop.html(`
			<div class="hm-pop-head" style="background:${color}">
				${img}
				<div>
					<div class="hm-pop-name">${frappe.utils.escape_html(emp.employee_name)}</div>
					<div class="hm-pop-desig">${frappe.utils.escape_html(emp.designation || "")}</div>
				</div>
			</div>
			<div class="hm-pop-body">
				${row("🏢", emp.department)}
				${row("📍", emp.branch)}
				${row("👤", mgr ? __("Reports to {0}", [mgr.employee_name]) : __("Top level"))}
				${row("✉️", emp.company_email)}
				${row("📞", emp.cell_number)}
				${row("📅", emp.date_of_joining ? __("Joined {0}", [frappe.datetime.str_to_user(emp.date_of_joining)]) : "")}
				<div class="hm-pop-counts">
					<span><b>${direct}</b> ${__("Direct")}</span>
					<span><b>${total}</b> ${__("Total team")}</span>
				</div>
				<div class="hm-pop-hint">${__("Click card to open employee")}</div>
			</div>
		`);

		const rect = $card[0].getBoundingClientRect();
		this.$pop.css({ display: "block", visibility: "hidden", left: 0, top: 0 });
		const pw = this.$pop.outerWidth(), ph = this.$pop.outerHeight();
		let left = rect.right + 10, top = rect.top;
		if (left + pw > window.innerWidth - 10) left = rect.left - pw - 10;
		if (left < 10) left = Math.max(10, (window.innerWidth - pw) / 2);
		if (top + ph > window.innerHeight - 10) top = window.innerHeight - ph - 10;
		this.$pop.css({ left, top: Math.max(10, top), visibility: "visible" });
	}

	hide_popover() {
		this._pop_t = setTimeout(() => this.$pop.hide(), 150);
	}

	// ================================================================ search
	apply_search(txt) {
		txt = (txt || "").toLowerCase().trim();
		this.$body.find(".hm-card").removeClass("hm-hit hm-dim");
		if (!txt) return;

		const hits = (this.data.employees || []).filter(
			(e) =>
				e.employee_name.toLowerCase().includes(txt) ||
				(e.designation || "").toLowerCase().includes(txt) ||
				(e.department || "").toLowerCase().includes(txt)
		);
		if (!hits.length) {
			frappe.show_alert({ message: __("No match"), indicator: "orange" });
			return;
		}

		hits.forEach((h) => {
			let cur = h.reports_to;
			while (cur) { this.collapsed.delete(cur); cur = (this.by_id[cur] || {}).reports_to; }
		});
		this.render();

		this.$body.find(".hm-card").addClass("hm-dim");
		hits.forEach((h) =>
			this.$body.find(`.hm-card[data-emp="${h.name}"]`).removeClass("hm-dim").addClass("hm-hit")
		);
		const el = this.$body.find(`.hm-card[data-emp="${hits[0].name}"]`)[0];
		if (el) el.scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
	}

	// ================================================================ export / print
	export_excel() {
		const url = `/api/method/${API}.export_org_excel?company=${encodeURIComponent(this.company || "")}`;
		window.open(frappe.urllib.get_full_url(url));
	}

	print_chart() {
		const collapsed_backup = new Set(this.collapsed);
		this.collapsed.clear();
		this.render();
		const html = this.$tree.html();
		this.collapsed = collapsed_backup;
		this.render();

		const is_v = this.layout === "vertical";
		const css = $("#hm-org-css").html();
		const w = window.open("", "_blank");
		w.document.write(`<!DOCTYPE html><html><head><title>${__("Organization Structure")}</title>
			<style>${css}
				@page { size: ${is_v ? "A4 portrait" : "A3 landscape"}; margin: 10mm; }
				body { margin:0; font-family: Inter, Arial, sans-serif; }
				.hm-print-head { display:flex; justify-content:space-between; align-items:baseline;
					border-bottom:3px solid ${HM_BLUE}; padding:6px 2px 8px; margin-bottom:14px; }
				.hm-print-head h2 { margin:0; color:${HM_BLUE}; font-size:20px; }
				.hm-print-head span { color:#666; font-size:11px; }
				.hm-print-tree { transform-origin: top left; }
				.hm-card { box-shadow:none !important; cursor:default; break-inside: avoid; }
				.hm-toggle { display:none; }
				.hm-toggle-spacer { display:none; }
				.hm-v-row { break-inside: avoid; }
			</style></head><body>
			<div class="hm-print-head">
				<h2>${__("Organization Structure")}${this.company ? " — " + frappe.utils.escape_html(this.company) : ""}</h2>
				<span>${frappe.datetime.str_to_user(frappe.datetime.now_date())} · ${(this.data.stats || {}).total || 0} ${__("Employees")}</span>
			</div>
			<div class="hm-print-tree">${html}</div>
			</body></html>`);
		w.document.close();

		w.onload = () => {
			if (!is_v) {
				const tree = w.document.querySelector(".hm-print-tree");
				const scale = Math.min(1, (w.document.body.clientWidth - 20) / tree.scrollWidth);
				tree.style.transform = `scale(${scale})`;
			}
			setTimeout(() => { w.print(); }, 400);
		};
	}

	// ================================================================ css
	inject_css() {
		if ($("#hm-org-css").length) return;
		$(`<style id="hm-org-css">
			.hm-org-bar { display:flex; justify-content:space-between; align-items:center;
				flex-wrap:wrap; gap:8px; margin:4px 4px 10px; }
			.hm-org-stats { display:flex; gap:16px; color:var(--text-muted,#666); font-size:13px; }
			.hm-org-stats b { color:${HM_BLUE}; font-size:15px; }
			.hm-org-legend { display:flex; flex-wrap:wrap; gap:10px; font-size:11px; color:var(--text-muted,#666); }
			.hm-lg i { display:inline-block; width:9px; height:9px; border-radius:2px; margin-right:4px; }

			.hm-org-viewport { position:relative; height: calc(100vh - 220px); min-height:420px;
				overflow:auto; border:1px solid var(--border-color,#e2e2e2); border-radius:12px;
				background:var(--bg-color,#fafbfc); }
			.hm-org-viewport.hm-mode-tree { cursor:grab;
				background:
					radial-gradient(circle, var(--border-color,#e8e8e8) 1px, transparent 1px) 0 0/22px 22px,
					var(--bg-color,#fafbfc); }
			.hm-org-viewport.hm-grabbing { cursor:grabbing; user-select:none; }
			.hm-org-canvas { padding:24px; min-width:100%; min-height:100%; }
			.hm-mode-vertical .hm-org-canvas { padding:18px 24px; }
			.hm-org-tree { transform-origin: top left; }
			.hm-mode-tree .hm-org-tree { width:max-content; }
			.hm-org-empty { color:var(--text-muted,#666); padding:60px; text-align:center; }

			.hm-zoom-ctl { position:sticky; float:right; top:12px; margin-right:12px; z-index:5;
				display:flex; align-items:center; gap:4px; background:var(--card-bg,#fff);
				border:1px solid var(--border-color,#e2e2e2); border-radius:8px; padding:4px 8px;
				box-shadow:0 2px 8px rgba(0,0,0,.08); }
			.hm-zoom-ctl button { border:none; background:transparent; cursor:pointer; font-size:13px;
				padding:3px 7px; border-radius:5px; color:var(--text-color,#333); }
			.hm-zoom-ctl button:hover { background:rgba(1,11,206,.08); color:${HM_BLUE}; }
			.hm-zoom-pct { font-size:11px; color:var(--text-muted,#888); min-width:34px; text-align:right; }

			/* ============ VERTICAL (indented) layout ============ */
			.hm-v-wrap { max-width: 720px; }
			.hm-v-node { position:relative; }
			.hm-v-row { padding:4px 0; position:relative; }
			.hm-v-kids { margin-left:19px; padding-left:26px; position:relative;
				border-left:2px solid var(--border-color,#dcdcdc); }
			.hm-v-kids > .hm-v-node > .hm-v-row::before { content:""; position:absolute;
				left:-26px; top:50%; width:22px; height:2px;
				background:var(--border-color,#dcdcdc); }
			.hm-v-kids > .hm-v-node:last-child { }
			/* mask the parent rail below the last child's elbow */
			.hm-v-kids > .hm-v-node:last-child::after { content:""; position:absolute;
				left:-28px; top:calc(50% - 0px); bottom:0; width:2px;
				background:var(--bg-color,#fafbfc); }
			.hm-v-kids > .hm-v-node:last-child::after { top:26px; }

			.hm-tags { display:flex; flex-direction:column; align-items:flex-end; gap:4px; flex:none; }
			.hm-chip { font-size:10.5px; padding:2px 9px; border-radius:10px; white-space:nowrap; }
			.hm-count { font-size:10.5px; color:var(--text-muted,#999); white-space:nowrap; }
			.hm-toggle-v, .hm-toggle-spacer { position:static; transform:none; flex:none;
				align-self:center; margin-right:2px; }
			.hm-toggle-spacer { display:inline-block; width:24px; }

			/* ============ TREE (top-down) layout ============ */
			.hm-lvl { display:flex; padding-top:28px; margin:0; justify-content:center; }
			.hm-lvl.hm-root { padding-top:0; }
			.hm-lvl li { list-style:none; position:relative; padding:0 12px; text-align:center; }
			.hm-lvl li::before, .hm-lvl li::after { content:""; position:absolute; top:-28px;
				width:50%; height:28px; border-top:2px solid var(--border-color,#d5d5d5); }
			.hm-lvl li::before { left:-1px; border-right:2px solid var(--border-color,#d5d5d5); }
			.hm-lvl li::after { right:-1px; }
			.hm-lvl li:only-child::before, .hm-lvl li:only-child::after { display:none; }
			.hm-lvl li:first-child::before { border:none; }
			.hm-lvl li:first-child::after { border-radius:10px 0 0 0; border-left:2px solid var(--border-color,#d5d5d5); }
			.hm-lvl li:last-child::before { border-right:none; border-radius:0 10px 0 0; }
			.hm-lvl li:last-child::after { border:none; }
			.hm-lvl.hm-root > li::before, .hm-lvl.hm-root > li::after { display:none; }
			.hm-lvl li > ul { position:relative; }
			.hm-lvl li > ul::before { content:""; position:absolute; top:0; left:50%; width:2px;
				height:28px; background:var(--border-color,#d5d5d5); transform:translateX(-50%); }

			/* ============ shared card ============ */
			.hm-card { display:inline-flex; align-items:center; gap:10px; text-align:left;
				background:var(--card-bg,#fff); border:1px solid var(--border-color,#e2e2e2);
				border-left:4px solid var(--dept, ${HM_BLUE}); border-radius:10px;
				padding:9px 13px; min-width:190px; max-width:240px; position:relative;
				box-shadow:0 1px 3px rgba(0,0,0,.05); cursor:pointer;
				transition:box-shadow .15s, transform .15s; }
			.hm-card:hover { box-shadow:0 6px 18px rgba(1,11,206,.16); transform:translateY(-1px); }
			.hm-card.hm-hit { border-color:${HM_RED}; box-shadow:0 0 0 3px rgba(213,0,0,.18); }
			.hm-card.hm-dim { opacity:.35; }
			.hm-avatar img, .hm-initials { width:38px; height:38px; border-radius:50%; object-fit:cover;
				display:flex; align-items:center; justify-content:center; flex:none;
				color:#fff; font-weight:600; font-size:13px; }
			.hm-name { font-weight:600; font-size:13px; color:var(--text-color,#222);
				white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:150px; }
			.hm-desig { font-size:11.5px; color:var(--text-muted,#777);
				white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:150px; }
			.hm-toggle { position:absolute; bottom:-12px; left:50%; transform:translateX(-50%);
				background:${HM_BLUE}; color:#fff; border:none; border-radius:12px;
				min-width:24px; height:24px; padding:0 7px; font-size:12px; line-height:1;
				cursor:pointer; z-index:2; }
			.hm-toggle:hover { background:#0008a8; }

			/* vertical card overrides — MUST stay after the shared .hm-card block */
			.hm-card.hm-card-v { display:flex; width:100%; min-width:0; max-width:680px;
				border-left:1px solid var(--border-color,#e2e2e2);
				box-shadow:inset 4px 0 0 var(--dept,${HM_BLUE}), 0 1px 3px rgba(0,0,0,.05); }
			.hm-card.hm-card-v:hover { box-shadow:inset 4px 0 0 var(--dept,${HM_BLUE}), 0 6px 18px rgba(1,11,206,.16); }
			.hm-card.hm-card-v .hm-meta { flex:1 1 auto; min-width:80px; overflow:hidden; }
			.hm-card.hm-card-v .hm-name,
			.hm-card.hm-card-v .hm-desig { max-width:none; }
			.hm-card.hm-card-v .hm-toggle { position:static; transform:none; flex:none;
				align-self:center; margin-right:2px; }

			/* ============ popover ============ */
			.hm-pop { position:fixed; z-index:1050; width:280px; background:var(--card-bg,#fff);
				border-radius:12px; overflow:hidden; box-shadow:0 12px 40px rgba(0,0,0,.22);
				border:1px solid var(--border-color,#e2e2e2); font-size:12.5px; }
			.hm-pop-head { display:flex; gap:12px; align-items:center; padding:14px; color:#fff; }
			.hm-pop-head img, .hm-pop-initials { width:52px; height:52px; border-radius:50%;
				object-fit:cover; border:2px solid rgba(255,255,255,.6); display:flex;
				align-items:center; justify-content:center; color:#fff; font-weight:700;
				font-size:17px; flex:none; }
			.hm-pop-name { font-weight:700; font-size:14.5px; }
			.hm-pop-desig { opacity:.85; font-size:12px; }
			.hm-pop-body { padding:10px 14px 12px; }
			.hm-pop-row { display:flex; gap:8px; padding:3px 0; color:var(--text-color,#333); }
			.hm-pop-counts { display:flex; gap:16px; margin-top:8px; padding-top:8px;
				border-top:1px dashed var(--border-color,#e2e2e2); }
			.hm-pop-counts b { color:${HM_BLUE}; }
			.hm-pop-hint { margin-top:8px; font-size:10.5px; color:var(--text-muted,#999); }
		</style>`).appendTo("head");
	}
}