// Copyright (c) 2026, HM
// ET General Ledger - enhanced General Ledger report

const ET_GL_METHOD = "gicore.gi_accounting.report.et_general_ledger.et_general_ledger";
const ET_BRAND_BLUE = "#010BCE";
const ET_BRAND_RED = "#D50000";

frappe.query_reports["ET General Ledger"] = {
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "finance_book",
			label: __("Finance Book"),
			fieldtype: "Link",
			options: "Finance Book",
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
			width: "60px",
		},
		{
			fieldname: "account",
			label: __("Account"),
			fieldtype: "MultiSelectList",
			options: "Account",
			get_data: function (txt) {
				return frappe.db.get_link_options("Account", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		// ---- NEW FILTERS ----
		{
			fieldname: "voucher_type",
			label: __("Voucher Type"),
			fieldtype: "Autocomplete",
			options: [
				"Journal Entry",
				"Sales Invoice",
				"Purchase Invoice",
				"Payment Entry",
				"Delivery Note",
				"Purchase Receipt",
				"Stock Entry",
				"Expense Claim",
				"Period Closing Voucher",
				"Landed Cost Voucher",
				"Asset",
				"POS Invoice",
				"Bank Transaction",
			],
		},
		{
			fieldname: "account_type",
			label: __("Account Type"),
			fieldtype: "Autocomplete",
			options: [
				"Bank",
				"Cash",
				"Receivable",
				"Payable",
				"Stock",
				"Fixed Asset",
				"Tax",
				"Chargeable",
				"Expense Account",
				"Income Account",
				"Depreciation",
				"Equity",
				"Round Off",
				"Temporary",
			],
		},
		{
			fieldname: "root_type",
			label: __("Root Type"),
			fieldtype: "Select",
			options: ["", "Asset", "Liability", "Equity", "Income", "Expense"],
		},
		{
			fieldname: "created_by",
			label: __("Created By"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "voucher_no",
			label: __("Voucher No"),
			fieldtype: "Data",
		},
		{
			fieldname: "against_voucher_no",
			label: __("Against Voucher No"),
			fieldtype: "Data",
		},
		{
			fieldtype: "Break",
		},
		{
			fieldname: "party_type",
			label: __("Party Type"),
			fieldtype: "Autocomplete",
			options: Object.keys(frappe.boot.party_account_types || {}),
			on_change: function () {
				frappe.query_report.set_filter_value("party", []);
			},
		},
		{
			fieldname: "party",
			label: __("Party"),
			fieldtype: "MultiSelectList",
			options: "party_type",
			get_data: function (txt) {
				if (!frappe.query_report.filters) return;
				let party_type = frappe.query_report.get_filter_value("party_type");
				if (!party_type) return;
				return frappe.db.get_link_options(party_type, txt);
			},
		},
		{
			fieldname: "cost_center",
			label: __("Cost Center"),
			fieldtype: "MultiSelectList",
			options: "Cost Center",
			get_data: function (txt) {
				return frappe.db.get_link_options("Cost Center", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "project",
			label: __("Project"),
			fieldtype: "MultiSelectList",
			options: "Project",
			get_data: function (txt) {
				return frappe.db.get_link_options("Project", txt, {
					company: frappe.query_report.get_filter_value("company"),
				});
			},
		},
		{
			fieldname: "presentation_currency",
			label: __("Currency"),
			fieldtype: "Select",
			options: erpnext.get_presentation_currency_list(),
		},
		// ---- NEW GROUPING TOGGLES (collapsible) ----
		{
			fieldname: "group_by_month",
			label: __("Group by Month"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "group_by_party",
			label: __("Group by Party"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "group_by_party_name",
			label: __("Group by Party Name"),
			fieldtype: "Check",
			default: 0,
		},
		{
			fieldname: "show_dashboard",
			label: __("Show Dashboard"),
			fieldtype: "Check",
			default: 0,
		},
		// ---- BIG DATA PAGINATION ----
		{
			fieldname: "page_length",
			label: __("Rows per Page"),
			fieldtype: "Select",
			options: ["500", "1000", "2500", "5000", "10000", "25000", "50000"],
			default: "1000",
		},
		{
			fieldname: "page_no",
			label: __("Page No"),
			fieldtype: "Int",
			default: 1,
		},
		// ---- Standard toggles ----
		{
			fieldname: "show_opening_entries",
			label: __("Show Opening Entries"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_cancelled_entries",
			label: __("Show Cancelled Entries"),
			fieldtype: "Check",
		},
		{
			fieldname: "show_remarks",
			label: __("Show Remarks"),
			fieldtype: "Check",
		},
	],

	// Collapsible tree: rows carry `indent`, so the datatable renders
	// month / party groups as expandable nodes.
	initial_depth: 1,

	onload: function (report) {
		et_gl.bind_eye_icon();

		// ---- Pagination buttons ----
		report.page.add_inner_button(__("◀ Prev Page"), () => et_gl.change_page(-1), __("Pages"));
		report.page.add_inner_button(__("Next Page ▶"), () => et_gl.change_page(1), __("Pages"));
		report.page.add_inner_button(__("First Page"), () => {
			frappe.query_report.set_filter_value("page_no", 1);
		}, __("Pages"));

		// ---- Print buttons (multiple designs) ----
		report.page.add_inner_button(__("Classic Ledger"), () => et_gl.print_report("classic"), __("🖨 Print"));
		report.page.add_inner_button(__("Brand (HM)"), () => et_gl.print_report("brand"), __("🖨 Print"));
		report.page.add_inner_button(__("Summary Only"), () => et_gl.print_report("summary"), __("🖨 Print"));

		// ---- Dashboard button ----
		report.page.add_inner_button(__("📊 Dashboard"), () => et_gl.show_dashboard());
	},

	after_datatable_render: function () {
		// Auto-open dashboard popup when the checkbox is on (once per refresh)
		if (
			cint(frappe.query_report.get_filter_value("show_dashboard")) &&
			!et_gl._dashboard_shown_for_this_refresh
		) {
			et_gl._dashboard_shown_for_this_refresh = true;
			setTimeout(() => {
				et_gl.show_dashboard();
				// allow again on next refresh
				setTimeout(() => (et_gl._dashboard_shown_for_this_refresh = false), 1500);
			}, 300);
		}
	},

	formatter: function (value, row, column, data, default_formatter) {
		value = default_formatter(value, row, column, data);

		if (data && data.is_group_header) {
			value = `<span style="font-weight:600;">${value}</span>`;
			if (data.is_summary_row && column.fieldname === "account") {
				value = `<span style="color:${ET_BRAND_BLUE};">${value}</span>`;
			}
		}

		// Eye icon + quick actions on Voucher No
		if (
			column.fieldname === "voucher_no" &&
			data &&
			data.voucher_no &&
			!data.is_group_header
		) {
			const vt = encodeURIComponent(data.voucher_type || "");
			const vn = encodeURIComponent(data.voucher_no || "");
			value += `
				<span class="et-gl-actions" style="margin-left:6px; white-space:nowrap;">
					<a class="et-gl-eye" data-vt="${vt}" data-vn="${vn}" title="${__("View GL details")}"
						style="cursor:pointer; color:${ET_BRAND_BLUE};">
						<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
							stroke-width="2" style="vertical-align:middle;">
							<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
							<circle cx="12" cy="12" r="3"/>
						</svg>
					</a>
					<a class="et-gl-newtab" data-vt="${vt}" data-vn="${vn}" title="${__("Open in new tab")}"
						style="cursor:pointer; color:var(--text-muted); margin-left:3px;">
						<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor"
							stroke-width="2" style="vertical-align:middle;">
							<path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
							<polyline points="15 3 21 3 21 9"/>
							<line x1="10" y1="14" x2="21" y2="3"/>
						</svg>
					</a>
				</span>`;
		}
		return value;
	},
};

// ===========================================================================
// et_gl namespace
// ===========================================================================
window.et_gl = {
	_eye_bound: false,
	_dashboard_shown_for_this_refresh: false,

	change_page(delta) {
		let page = cint(frappe.query_report.get_filter_value("page_no")) || 1;
		page = Math.max(1, page + delta);
		frappe.query_report.set_filter_value("page_no", page);
	},

	bind_eye_icon() {
		if (this._eye_bound) return;
		this._eye_bound = true;

		$(document).on("click", ".et-gl-eye", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const vt = decodeURIComponent($(this).attr("data-vt"));
			const vn = decodeURIComponent($(this).attr("data-vn"));
			et_gl.show_voucher_popup(vt, vn);
		});

		$(document).on("click", ".et-gl-newtab", function (e) {
			e.preventDefault();
			e.stopPropagation();
			const vt = decodeURIComponent($(this).attr("data-vt"));
			const vn = decodeURIComponent($(this).attr("data-vn"));
			et_gl.open_in_new_tab(vt, vn);
		});
	},

	open_in_new_tab(voucher_type, voucher_no) {
		const url = `/app/${frappe.router.slug(voucher_type)}/${encodeURIComponent(voucher_no)}`;
		window.open(url, "_blank");
	},

	// ---------------------------------------------------------------------
	// Voucher details popup (eye icon)
	// ---------------------------------------------------------------------
	show_voucher_popup(voucher_type, voucher_no) {
		frappe.call({
			method: `${ET_GL_METHOD}.get_voucher_details`,
			args: { voucher_type, voucher_no },
			freeze: true,
			callback: (r) => {
				if (!r.message) return;
				const m = r.message;
				const cur = frappe.query_report.get_filter_value("presentation_currency") || "";

				let info_html = "";
				if (m.doc_info) {
					info_html = `
						<div class="row" style="margin-bottom:10px; font-size:12px;">
							<div class="col-sm-3"><b>${__("Status")}</b><br>${m.doc_info.docstatus_label || ""}</div>
							<div class="col-sm-3"><b>${__("Created By")}</b><br>${frappe.utils.escape_html(m.doc_info.owner_name || m.doc_info.owner || "")}</div>
							<div class="col-sm-3"><b>${__("Created")}</b><br>${frappe.datetime.str_to_user(m.doc_info.creation)}</div>
							<div class="col-sm-3"><b>${__("Modified")}</b><br>${frappe.datetime.str_to_user(m.doc_info.modified)}</div>
						</div>`;
				}

				let rows = (m.gl_entries || [])
					.map(
						(g) => `
					<tr ${g.is_cancelled ? 'style="text-decoration:line-through; color:#999;"' : ""}>
						<td>${frappe.datetime.str_to_user(g.posting_date)}</td>
						<td>${frappe.utils.escape_html(g.account || "")}</td>
						<td>${frappe.utils.escape_html(g.party || "")}</td>
						<td class="text-right">${format_currency(g.debit, cur)}</td>
						<td class="text-right">${format_currency(g.credit, cur)}</td>
						<td>${frappe.utils.escape_html(g.against || "")}</td>
					</tr>`
					)
					.join("");

				const body = `
					${info_html}
					<div style="max-height:340px; overflow:auto; border:1px solid var(--border-color); border-radius:6px;">
						<table class="table table-bordered table-sm" style="margin:0; font-size:12px;">
							<thead style="position:sticky; top:0; background:${ET_BRAND_BLUE}; color:#fff;">
								<tr>
									<th>${__("Date")}</th><th>${__("Account")}</th><th>${__("Party")}</th>
									<th class="text-right">${__("Debit")}</th>
									<th class="text-right">${__("Credit")}</th>
									<th>${__("Against")}</th>
								</tr>
							</thead>
							<tbody>${rows}</tbody>
							<tfoot>
								<tr style="font-weight:600; background:var(--bg-light-gray);">
									<td colspan="3">${__("Total")}</td>
									<td class="text-right">${format_currency(m.total_debit, cur)}</td>
									<td class="text-right">${format_currency(m.total_credit, cur)}</td>
									<td></td>
								</tr>
							</tfoot>
						</table>
					</div>`;

				const d = new frappe.ui.Dialog({
					title: `${voucher_type}: ${voucher_no}`,
					size: "extra-large",
					fields: [{ fieldtype: "HTML", fieldname: "body" }],
					primary_action_label: __("Open in New Tab"),
					primary_action: () => et_gl.open_in_new_tab(voucher_type, voucher_no),
				});
				d.fields_dict.body.$wrapper.html(body);
				d.show();
			},
		});
	},

	// ---------------------------------------------------------------------
	// Print designs
	// ---------------------------------------------------------------------
	print_report(style) {
		const qr = frappe.query_report;
		if (!qr.data || !qr.data.length) {
			frappe.msgprint(__("Nothing to print. Run the report first."));
			return;
		}

		const filters = qr.get_filter_values();
		const visible_cols = qr.columns.filter((c) => !c.hidden && c.fieldname !== "gl_entry");
		let data = qr.data;
		if (style === "summary") {
			data = data.filter((d) => d.is_group_header);
			if (!data.length) {
				frappe.msgprint(__("Enable a Group By option to print a summary."));
				return;
			}
		}

		const fmt = (col, val, row) => {
			if (val === null || val === undefined) return "";
			if (["debit", "credit", "balance"].includes(col.fieldname)) {
				return val ? format_currency(val, filters.presentation_currency) : "";
			}
			if (col.fieldname === "posting_date" && val) return frappe.datetime.str_to_user(val);
			return frappe.utils.escape_html(String(val));
		};

		const head_cells = visible_cols.map((c) => `<th>${__(c.label)}</th>`).join("");
		const body_rows = data
			.map((row) => {
				const cls = row.is_group_header ? ' class="grp"' : "";
				const pad = row.indent ? `style="padding-left:${row.indent * 16}px;"` : "";
				const cells = visible_cols
					.map((c, i) => {
						const align = ["debit", "credit", "balance"].includes(c.fieldname)
							? ' class="num"'
							: "";
						const p = i === 1 && row.indent ? pad : ""; // indent the Account cell
						return `<td${align} ${p}>${fmt(c, row[c.fieldname], row)}</td>`;
					})
					.join("");
				return `<tr${cls}>${cells}</tr>`;
			})
			.join("");

		const styles = et_gl.get_print_css(style);
		const title = style === "summary" ? __("General Ledger — Summary") : __("General Ledger");
		const html = `
			<!DOCTYPE html><html><head><meta charset="utf-8"><title>${title}</title>
			<style>${styles}</style></head>
			<body>
				<div class="hdr">
					<div>
						<h1>${title}</h1>
						<div class="sub">${frappe.utils.escape_html(filters.company || "")}</div>
						<div class="sub">${frappe.datetime.str_to_user(filters.from_date)} — ${frappe.datetime.str_to_user(filters.to_date)}</div>
					</div>
					<div class="meta">
						${__("Printed")}: ${frappe.datetime.now_datetime()}<br>
						${__("By")}: ${frappe.utils.escape_html(frappe.session.user_fullname || frappe.session.user)}
					</div>
				</div>
				<table><thead><tr>${head_cells}</tr></thead><tbody>${body_rows}</tbody></table>
				<div class="ftr">ET General Ledger — HM</div>
				<script>window.onload = () => setTimeout(() => window.print(), 300);<\/script>
			</body></html>`;

		const w = window.open("", "_blank");
		w.document.write(html);
		w.document.close();
	},

	get_print_css(style) {
		const base = `
			* { box-sizing: border-box; }
			body { font-family: -apple-system, "Segoe UI", Arial, sans-serif; margin: 24px; color: #1f2937; font-size: 11px; }
			table { width: 100%; border-collapse: collapse; }
			th, td { padding: 5px 7px; border-bottom: 1px solid #e5e7eb; text-align: left; }
			td.num { text-align: right; font-variant-numeric: tabular-nums; }
			.hdr { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 16px; }
			.hdr h1 { margin: 0 0 4px; font-size: 20px; }
			.sub { color: #6b7280; font-size: 12px; }
			.meta { text-align: right; color: #6b7280; font-size: 10px; }
			.ftr { margin-top: 14px; text-align: center; color: #9ca3af; font-size: 9px; }
			tr.grp td { font-weight: 700; background: #f3f4f6; }
			@media print { body { margin: 8mm; } thead { display: table-header-group; } tr { page-break-inside: avoid; } }
		`;
		if (style === "brand" || style === "summary") {
			return (
				base +
				`
				.hdr { border-bottom: 4px solid ${ET_BRAND_BLUE}; padding-bottom: 10px; }
				.hdr h1 { color: ${ET_BRAND_BLUE}; }
				thead th { background: ${ET_BRAND_BLUE}; color: #fff; border: none; }
				tr.grp td { background: #eef0ff; color: ${ET_BRAND_BLUE}; border-top: 2px solid ${ET_BRAND_RED}; }
				.ftr { color: ${ET_BRAND_RED}; }
			`
			);
		}
		// classic
		return (
			base +
			`
			body { font-family: Georgia, "Times New Roman", serif; }
			thead th { border-top: 2px solid #000; border-bottom: 2px solid #000; background: #fff; }
			tr.grp td { background: #fff; border-top: 1px solid #000; }
		`
		);
	},

	// ---------------------------------------------------------------------
	// Dashboard popup
	// ---------------------------------------------------------------------
	show_dashboard() {
		const filters = frappe.query_report.get_filter_values();
		frappe.call({
			method: `${ET_GL_METHOD}.get_dashboard_data`,
			args: { filters: filters },
			freeze: true,
			freeze_message: __("Building dashboard..."),
			callback: (r) => {
				if (!r.message) return;
				et_gl.render_dashboard_dialog(r.message);
			},
		});
	},

	render_dashboard_dialog(m) {
		const cur = m.currency || "";
		const t = m.totals || {};
		const net = flt(t.debit) - flt(t.credit);

		const kpi = (label, value, color) => `
			<div style="flex:1; min-width:150px; background:#fff; border:1px solid #e5e7eb;
				border-top:3px solid ${color}; border-radius:8px; padding:12px 14px;
				box-shadow:0 1px 2px rgba(0,0,0,.05);">
				<div style="font-size:11px; color:#6b7280; text-transform:uppercase; letter-spacing:.4px;">${label}</div>
				<div style="font-size:18px; font-weight:700; margin-top:4px; color:#111827;">${value}</div>
			</div>`;

		const body = `
			<div style="display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px;">
				${kpi(__("GL Entries"), cint(t.cnt).toLocaleString(), ET_BRAND_BLUE)}
				${kpi(__("Vouchers"), cint(t.vouchers).toLocaleString(), ET_BRAND_BLUE)}
				${kpi(__("Total Debit"), format_currency(t.debit, cur), "#16a34a")}
				${kpi(__("Total Credit"), format_currency(t.credit, cur), ET_BRAND_RED)}
				${kpi(__("Net (Dr − Cr)"), format_currency(net, cur), net >= 0 ? "#16a34a" : ET_BRAND_RED)}
			</div>
			<div class="row">
				<div class="col-sm-7">
					<div style="font-weight:600; margin-bottom:4px;">${__("Monthly Debit vs Credit")}</div>
					<div id="et-gl-chart-month"></div>
				</div>
				<div class="col-sm-5">
					<div style="font-weight:600; margin-bottom:4px;">${__("Activity by Voucher Type")}</div>
					<div id="et-gl-chart-vtype"></div>
				</div>
			</div>
			<div class="row" style="margin-top:12px;">
				<div class="col-sm-6">${et_gl.top_table(__("Top 10 Accounts"), m.top_accounts, cur)}</div>
				<div class="col-sm-6">${et_gl.top_table(__("Top 10 Parties"), m.top_parties, cur)}</div>
			</div>`;

		const d = new frappe.ui.Dialog({
			title: __("📊 General Ledger Dashboard"),
			size: "extra-large",
			fields: [{ fieldtype: "HTML", fieldname: "body" }],
		});
		d.fields_dict.body.$wrapper.html(body);
		d.show();

		setTimeout(() => {
			if (m.by_month && m.by_month.length) {
				new frappe.Chart("#et-gl-chart-month", {
					data: {
						labels: m.by_month.map((x) => x.label),
						datasets: [
							{ name: __("Debit"), values: m.by_month.map((x) => flt(x.debit)) },
							{ name: __("Credit"), values: m.by_month.map((x) => flt(x.credit)) },
						],
					},
					type: "bar",
					height: 240,
					colors: [ET_BRAND_BLUE, ET_BRAND_RED],
				});
			}
			if (m.by_voucher_type && m.by_voucher_type.length) {
				new frappe.Chart("#et-gl-chart-vtype", {
					data: {
						labels: m.by_voucher_type.map((x) => x.label),
						datasets: [{ values: m.by_voucher_type.map((x) => flt(x.amount)) }],
					},
					type: "percentage",
					height: 240,
					colors: [ET_BRAND_BLUE, ET_BRAND_RED, "#16a34a", "#f59e0b", "#8b5cf6", "#06b6d4", "#ec4899", "#64748b"],
				});
			}
		}, 200);
	},

	top_table(title, rows, cur) {
		const body = (rows || [])
			.map(
				(x) => `
			<tr>
				<td style="max-width:220px; overflow:hidden; text-overflow:ellipsis;">${frappe.utils.escape_html(x.label || "")}</td>
				<td class="text-right">${format_currency(flt(x.debit), cur)}</td>
				<td class="text-right">${format_currency(flt(x.credit), cur)}</td>
			</tr>`
			)
			.join("");
		return `
			<div style="font-weight:600; margin-bottom:4px;">${title}</div>
			<div style="max-height:220px; overflow:auto; border:1px solid var(--border-color); border-radius:6px;">
				<table class="table table-sm" style="margin:0; font-size:11px;">
					<thead style="position:sticky; top:0; background:var(--bg-light-gray);">
						<tr><th></th><th class="text-right">${__("Debit")}</th><th class="text-right">${__("Credit")}</th></tr>
					</thead>
					<tbody>${body}</tbody>
				</table>
			</div>`;
	},
};

erpnext.utils.add_dimensions("ET General Ledger", 15);
