frappe.pages["org-structure"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Organization Structure"),
		single_column: true,
	});

	new OrgStructure(page, wrapper);
};

class OrgStructure {
	constructor(page, wrapper) {
		this.page = page;
		this.wrapper = wrapper;
		this.company = frappe.defaults.get_user_default("Company");
		this.collapsed = new Set();

		this.inject_css();
		this.make_toolbar();
		this.make_body();
		this.load();
	}

	// ------------------------------------------------------------------ toolbar
	make_toolbar() {
		this.company_field = this.page.add_field({
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: this.company,
			change: () => {
				this.company = this.company_field.get_value();
				this.load();
			},
		});

		this.search_field = this.page.add_field({
			fieldname: "search",
			label: __("Search Employee"),
			fieldtype: "Data",
			change: () => this.apply_search(this.search_field.get_value()),
		});

		this.page.set_primary_action(__("Expand All"), () => {
			this.collapsed.clear();
			this.render();
		});
		this.page.set_secondary_action(__("Collapse All"), () => {
			(this.data.employees || []).forEach((e) => {
				if (this.children_map[e.name]?.length) this.collapsed.add(e.name);
			});
			// keep roots visible
			this.roots.forEach((r) => this.collapsed.delete(r.name));
			this.render();
		});
	}

	make_body() {
		this.$body = $(`
			<div class="hm-org">
				<div class="hm-org-stats"></div>
				<div class="hm-org-canvas">
					<div class="hm-org-tree"></div>
				</div>
			</div>
		`).appendTo(this.page.main);
	}

	// ------------------------------------------------------------------ data
	load() {
		frappe.call({
			// adjust dotted path to your app/module
			method: "gicore.gi_hr.page.org_structure.org_structure.get_org_data",
			args: { company: this.company },
			freeze: true,
			callback: (r) => {
				this.data = r.message || { employees: [], stats: {} };
				this.index();
				this.render();
			},
		});
	}

	index() {
		this.by_id = {};
		this.children_map = {};
		(this.data.employees || []).forEach((e) => {
			this.by_id[e.name] = e;
			this.children_map[e.name] = [];
		});
		(this.data.employees || []).forEach((e) => {
			if (e.reports_to) this.children_map[e.reports_to].push(e);
		});
		this.roots = (this.data.employees || []).filter((e) => !e.reports_to);
	}

	total_reports(id) {
		let n = 0;
		const walk = (x) =>
			(this.children_map[x] || []).forEach((c) => {
				n++;
				walk(c.name);
			});
		walk(id);
		return n;
	}

	// ------------------------------------------------------------------ render
	render() {
		const s = this.data.stats || {};
		this.$body.find(".hm-org-stats").html(`
			<span><b>${s.total || 0}</b> ${__("Employees")}</span>
			<span><b>${s.departments || 0}</b> ${__("Departments")}</span>
			<span><b>${s.roots || 0}</b> ${__("Top-level")}</span>
		`);

		const $tree = this.$body.find(".hm-org-tree").empty();
		if (!this.roots.length) {
			$tree.html(`<div class="hm-org-empty">${__("No active employees found. Check reports_to links.")}</div>`);
			return;
		}
		const $rootUl = $('<ul class="hm-lvl hm-root"></ul>').appendTo($tree);
		this.roots.forEach((r) => this.render_node(r, $rootUl));
	}

	render_node(emp, $parentUl) {
		const kids = this.children_map[emp.name] || [];
		const is_collapsed = this.collapsed.has(emp.name);
		const $li = $("<li></li>").appendTo($parentUl);

		const avatar = emp.image
			? `<img src="${emp.image}" alt="">`
			: `<span class="hm-initials">${frappe.get_abbr(emp.employee_name)}</span>`;

		const $card = $(`
			<div class="hm-card" data-emp="${emp.name}">
				<div class="hm-avatar">${avatar}</div>
				<div class="hm-meta">
					<a class="hm-name" href="/app/employee/${emp.name}">${frappe.utils.escape_html(emp.employee_name)}</a>
					<div class="hm-desig">${frappe.utils.escape_html(emp.designation || "")}</div>
					${emp.department ? `<div class="hm-dept">${frappe.utils.escape_html(emp.department)}</div>` : ""}
				</div>
				${
					kids.length
						? `<button class="hm-toggle" title="${__("Expand / Collapse")}">
							${is_collapsed ? `+${this.total_reports(emp.name)}` : "&minus;"}
						  </button>`
						: ""
				}
			</div>
		`).appendTo($li);

		$card.find(".hm-toggle").on("click", (ev) => {
			ev.stopPropagation();
			is_collapsed ? this.collapsed.delete(emp.name) : this.collapsed.add(emp.name);
			this.render();
		});

		if (kids.length && !is_collapsed) {
			const $ul = $('<ul class="hm-lvl"></ul>').appendTo($li);
			kids.forEach((k) => this.render_node(k, $ul));
		}
	}

	// ------------------------------------------------------------------ search
	apply_search(txt) {
		txt = (txt || "").toLowerCase().trim();
		this.$body.find(".hm-card").removeClass("hm-hit");
		if (!txt) return;

		const hit = (this.data.employees || []).find(
			(e) =>
				e.employee_name.toLowerCase().includes(txt) ||
				(e.designation || "").toLowerCase().includes(txt)
		);
		if (!hit) return;

		// expand the whole path to the hit
		let cur = hit.reports_to;
		while (cur) {
			this.collapsed.delete(cur);
			cur = (this.by_id[cur] || {}).reports_to;
		}
		this.render();

		const $card = this.$body.find(`.hm-card[data-emp="${hit.name}"]`).addClass("hm-hit");
		if ($card.length) $card[0].scrollIntoView({ behavior: "smooth", block: "center", inline: "center" });
	}

	// ------------------------------------------------------------------ css
	inject_css() {
		if ($("#hm-org-css").length) return;
		$(`<style id="hm-org-css">
			.hm-org { padding: 8px 0 30px; }
			.hm-org-stats { display:flex; gap:18px; margin:0 4px 14px; color:var(--text-muted); font-size:13px; }
			.hm-org-stats b { color:#010BCE; font-size:15px; }
			.hm-org-canvas { overflow:auto; padding:10px 4px 40px; }
			.hm-org-empty { color:var(--text-muted); padding:40px; text-align:center; }

			/* tree connectors */
			.hm-lvl { display:flex; padding-top:26px; margin:0; justify-content:center; }
			.hm-lvl.hm-root { padding-top:0; }
			.hm-lvl li { list-style:none; position:relative; padding:0 10px; text-align:center; }
			.hm-lvl li::before, .hm-lvl li::after {
				content:""; position:absolute; top:-26px; width:50%; height:26px;
				border-top:2px solid var(--border-color);
			}
			.hm-lvl li::before { left:-1px; border-right:2px solid var(--border-color); }
			.hm-lvl li::after  { right:-1px; }
			.hm-lvl li:only-child::before, .hm-lvl li:only-child::after { display:none; }
			.hm-lvl li:only-child { padding-top:0; }
			.hm-lvl li:first-child::before { border:none; }
			.hm-lvl li:first-child::after  { border-radius:8px 0 0 0; border-left:2px solid var(--border-color); }
			.hm-lvl li:last-child::before  { border-right:none; border-radius:0 8px 0 0; }
			.hm-lvl li:last-child::after   { border:none; }
			.hm-lvl.hm-root > li::before, .hm-lvl.hm-root > li::after { display:none; }
			.hm-lvl li > ul { position:relative; }
			.hm-lvl li > ul::before {
				content:""; position:absolute; top:0; left:50%; width:2px; height:26px;
				background:var(--border-color); transform:translateX(-50%);
			}

			/* node card */
			.hm-card {
				display:inline-flex; align-items:center; gap:10px; text-align:left;
				background:var(--card-bg, #fff); border:1px solid var(--border-color);
				border-top:3px solid #010BCE; border-radius:10px;
				padding:10px 14px; min-width:210px; max-width:260px;
				box-shadow:0 1px 3px rgba(0,0,0,.06); position:relative;
				transition:box-shadow .15s, transform .15s;
			}
			.hm-card:hover { box-shadow:0 4px 14px rgba(1,11,206,.14); transform:translateY(-1px); }
			.hm-card.hm-hit { border-color:#D50000; box-shadow:0 0 0 3px rgba(213,0,0,.18); }
			.hm-avatar img, .hm-initials {
				width:40px; height:40px; border-radius:50%; object-fit:cover; display:flex;
				align-items:center; justify-content:center; flex:none;
			}
			.hm-initials { background:#010BCE; color:#fff; font-weight:600; font-size:14px; }
			.hm-name { font-weight:600; font-size:13.5px; color:var(--text-color); display:block; }
			.hm-name:hover { color:#010BCE; text-decoration:none; }
			.hm-desig { font-size:12px; color:var(--text-muted); }
			.hm-dept {
				display:inline-block; margin-top:3px; font-size:10.5px; padding:1px 8px;
				border-radius:10px; background:rgba(1,11,206,.08); color:#010BCE;
			}
			.hm-toggle {
				position:absolute; bottom:-12px; left:50%; transform:translateX(-50%);
				background:#010BCE; color:#fff; border:none; border-radius:12px;
				min-width:24px; height:24px; padding:0 7px; font-size:12px; line-height:1;
				cursor:pointer; z-index:2;
			}
			.hm-toggle:hover { background:#0008a8; }
		</style>`).appendTo("head");
	}
}