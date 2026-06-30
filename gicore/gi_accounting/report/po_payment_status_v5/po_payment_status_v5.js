frappe.query_reports["PO Payment Status V5"] = {
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
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
			reqd: 0,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 0,
		},
		{
			fieldname: "supplier_group",
			label: __("Supplier Group"),
			fieldtype: "Link",
			options: "Supplier Group",
			on_change: function () {
				frappe.query_report.set_filter_value("supplier", "");
				frappe.query_report.refresh();
			},
		},
		{
			fieldname: "supplier",
			label: __("Supplier"),
			fieldtype: "Link",
			options: "Supplier",
			get_query: function () {
				var group = frappe.query_report.get_filter_value("supplier_group");
				if (group) {
					return { filters: { supplier_group: group } };
				}
				return {};
			},
		},
		{
			fieldname: "status",
			label: __("Status"),
			fieldtype: "MultiSelect",
			options: "\nFully Paid\nPartially Paid\nNot Paid",
			default:["Partially Paid", "Not Paid" ],
		},
		{
			fieldname: "purchase_order",
			label: __("Purchase Order"),
			fieldtype: "Link",
			options: "Purchase Order",
			get_query: function () {
				var supplier = frappe.query_report.get_filter_value("supplier");
				var company = frappe.query_report.get_filter_value("company");
				var q = { filters: { docstatus: 1 } };
				if (supplier) q.filters.supplier = supplier;
				if (company) q.filters.company = company;
				return q;
			},
		},
		{
			fieldname: "show_vat",
			label: __("Show VAT"),
			fieldtype: "Check",
			default: 0,
			on_change: function () {
				frappe.query_report.refresh();
			}
		},
		{
			fieldname: "group_by_month",
			label: __("Group by Month"),
			fieldtype: "Check",
			default: 0,
			on_change: function () {
				frappe.query_report.refresh();
			}
		}
	],

	// ── Color-code, badge, and add the per-row PO Summary trigger ───────────
	formatter: function (value, row, column, data, default_formatter) {

		// Purchase Order column: either a group label (month/grand total) or
		// the PO link plus the "view summary" button.
		if (column.fieldname === "purchase_order") {
			if (data && (data.is_month_total || data.is_grand_total)) {
				return highlight_wrap(`<strong>${frappe.utils.escape_html(data.label || "")}</strong>`, data);
			}
			if (data && data.purchase_order) {
				const link = default_formatter(value, row, column, data);
				return `<span style="display:inline-flex;align-items:center;gap:6px;">
					
					<button type="button" class="btn-reset po-summary-trigger" data-po="${frappe.utils.escape_html(data.purchase_order)}"
						title="${__('View PO Summary')}"
						style="border:none;background:transparent;cursor:pointer;padding:2px;line-height:0;color:#2490ef;">
						${eye_icon()}
					</button>
					
					<a href="/app/purchase-order/${value}">${value.slice(-10)}</a>
				</span>`;
			}
			return value;
		}

		value = default_formatter(value, row, column, data);

		if (column.fieldname === "status") {
			if (data && data.status === "Fully Paid") {
				value = `<span style="color: #28a745; font-weight: bold;">✅ ${data.status}</span>`;
			} else if (data && data.status === "Not Paid") {
				value = `<span style="color: #dc3545; font-weight: bold;">❌ ${data.status}</span>`;
			} else if (data && data.status === "Partially Paid") {
				value = `<span style="color: #fd7e14; font-weight: bold;">🔄 ${data.status}</span>`;
			} else if (data && data.status === "Summary") {
				value = `<span style="color: #0056b3; font-weight: bold; font-size: 1.05em;">📊 ${__("Month Total")}</span>`;
			} else if (data && data.status === "Grand Total") {
				value = `<span style="font-weight: bold; font-size: 1.05em;">🏆 ${__("Grand Total")}</span>`;
			}
		}

		if (column.fieldname === "outstanding_amount" && data && data.outstanding_amount > 0) {
			value = `<span style="color: #dc3545; font-weight: bold;">${value}</span>`;
		}

		if (column.fieldname === "paid_amount" && data && data.paid_amount > 0) {
			value = `<span style="color: #28a745;">${value}</span>`;
		}

		if (column.fieldname === "po_amount" && data && data.po_amount > 0) {
			value = `<strong>${value}</strong>`;
		}

		if (column.fieldname === "yet_to_be_invoiced" && data && data.yet_to_be_invoiced > 0) {
			value = `<span style="color: #fd7e14;">${value}</span>`;
		}

		if (column.fieldname === "paid_vs_invoiced" && data) {
			if (data.paid_vs_invoiced < 0) {
				value = `<span style="color: #dc3545;">${value}</span>`;
			} else if (data.paid_vs_invoiced > 0) {
				value = `<span style="color: #28a745;">${value}</span>`;
			}
		}

		// Bleed-fill the whole cell for month-total / grand-total rows so the
		// grouping reads like a trial balance band, not just bold text.
		if (data && (data.is_month_total || data.is_grand_total)) {
			value = highlight_wrap(value, data);
		}

		return value;
	},

	// ── Buttons + delegated click handler for the PO Summary popup ──────────
	onload: function (report) {
		report.page.add_inner_button(__("Export to Excel"), function () {
			report.export_to_excel();
		});

		report.page.add_inner_button(__("Refresh"), function () {
			report.refresh();
		});

		report.page.add_inner_button(__("Print Report"), function () {
			print_attractive_report(report);
		});

		report.page.add_inner_button(__("Show KPIs"), function () {
			show_kpi_dialog(report);
		});

		// Delegated handler — bound once on the stable wrapper so it keeps
		// working after every refresh/sort re-renders the DataTable rows.
		$(report.page.wrapper)
			.off("click", ".po-summary-trigger")
			.on("click", ".po-summary-trigger", function (e) {
				e.preventDefault();
				e.stopPropagation();
				const po = $(this).attr("data-po");
				if (po) pos_render_dialog(po);
			});

		// if (!$(report.page.wrapper).find(".po-report-note").length) {
		// 	$(report.page.wrapper).find(".page-head").append(`
		// 		<div class="text-muted small po-report-note" style="margin-top: 5px;">
		// 			ℹ️ ${__("Click the")} <span style="display:inline-block;vertical-align:middle;">${eye_icon()}</span> ${__("icon next to any Purchase Order for its full summary — items, receipts, invoices and payments.")}
		// 		</div>
		// 	`);
		// }
	},
};

// ============================================================================
// SHARED HELPERS
// ============================================================================

function eye_icon() {
	return `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"
		stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
		<circle cx="12" cy="12" r="3"></circle></svg>`;
}

// Bleed a cell's content into a full-width colored band — used for the
// month-total / grand-total rows so grouped data reads like a trial balance.
function highlight_wrap(html, data) {
	if (data && data.is_grand_total) {
		return `<span style="display:block;margin:-7px -10px;padding:7px 10px;background:#1b5fb0;color:#fff;font-weight:700;">${html}</span>`;
	}
	if (data && data.is_month_total) {
		return `<span style="display:block;margin:-7px -10px;padding:7px 10px;background:#eef3fb;font-weight:600;">${html}</span>`;
	}
	return html;
}

// ============================================================================
// ATTRACTIVE PRINT
// ============================================================================

function print_attractive_report(report) {
	if (!report.data || !report.data.length) {
		frappe.msgprint(__("No data to print. Please run the report first."));
		return;
	}
	const html = build_print_html(report);
	const win = window.open("", "_blank");
	if (!win) {
		frappe.msgprint(__("Please allow popups for this site to print the report."));
		return;
	}
	win.document.write(html);
	win.document.close();
	win.focus();
	setTimeout(() => win.print(), 350);
}

function build_print_html(report) {
	const columns = (frappe.query_report.get_visible_columns && frappe.query_report.get_visible_columns()) || report.columns || [];
	const rows = report.data || [];
	const company = frappe.query_report.get_filter_value("company") || "";
	const from_date = frappe.query_report.get_filter_value("from_date");
	const to_date = frappe.query_report.get_filter_value("to_date");
	const company_currency = frappe.boot.sysdefaults.currency;

	const header_cells = columns
		.map(c => `<th style="text-align:${c.fieldtype === "Currency" ? "right" : "left"};">${frappe.utils.escape_html(c.label || c.fieldname)}</th>`)
		.join("");

	const body_rows = rows.map(row => {
		const is_total = !!row.is_month_total;
		const is_grand = !!row.is_grand_total;
		const cells = columns.map(c => {
			let val = row[c.fieldname];
			if (c.fieldname === "purchase_order" && (is_total || is_grand)) {
				val = row.label || "";
			}
			if (c.fieldtype === "Currency" && typeof val === "number") {
				const cur = c.fieldname === "po_amount" ? (row.po_currency || company_currency) : (row.currency || company_currency);
				val = format_currency(val, cur);
			}
			const align = c.fieldtype === "Currency" ? "right" : "left";
			return `<td style="text-align:${align};">${val === null || val === undefined ? "" : frappe.utils.escape_html(String(val))}</td>`;
		}).join("");
		const row_class = is_grand ? "grand-row" : (is_total ? "month-row" : "");
		return `<tr class="${row_class}">${cells}</tr>`;
	}).join("");

	return `<!DOCTYPE html><html><head><meta charset="utf-8"><title>${__("PO Payment Status Report")}</title>
	<style>
		* { box-sizing: border-box; }
		body { font-family: -apple-system, "Segoe UI", Roboto, Arial, sans-serif; padding:28px; color:#1a1a1a; }
		h1 { font-size:19px; margin:0 0 2px; }
		.meta { color:#666; font-size:12px; margin-bottom:18px; }
		table { width:100%; border-collapse:collapse; font-size:11px; }
		th { background:#1b5fb0; color:#fff; padding:6px 8px; }
		td { padding:5px 8px; border-bottom:1px solid #e9ecef; white-space:nowrap; }
		tbody tr:nth-child(even) td { background:#f7f9fc; }
		tr.month-row td { background:#eef3fb !important; font-weight:600; }
		tr.grand-row td { background:#1b5fb0 !important; color:#fff; font-weight:700; }
		.footer-note { margin-top:16px; font-size:10px; color:#999; }
		@media print { body{padding:0;} }
	</style>
	</head><body>
		<h1>${__("Purchase Order Payment Status Report")}</h1>
		<div class="meta">
			${company ? __("Company") + ": " + frappe.utils.escape_html(company) + " &nbsp;|&nbsp; " : ""}
			${from_date ? __("From") + ": " + frappe.datetime.str_to_user(from_date) + " &nbsp;" : ""}
			${to_date ? __("To") + ": " + frappe.datetime.str_to_user(to_date) + " &nbsp;|&nbsp; " : ""}
			${__("Generated")}: ${frappe.datetime.str_to_user(frappe.datetime.now_datetime())}
		</div>
		<table>
			<thead><tr>${header_cells}</tr></thead>
			<tbody>${body_rows}</tbody>
		</table>
		<div class="footer-note">${__("Amounts are estimates where a Purchase Invoice spans multiple Purchase Orders (prorated by item value).")}</div>
	</body></html>`;
}

// ============================================================================
// KPI DIALOG
// ============================================================================

function show_kpi_dialog(report) {
	const all_rows = report.data || [];
	const rows = all_rows.filter(r => !r.is_month_total && !r.is_grand_total);

	if (!rows.length) {
		frappe.msgprint(__("No data available. Please run the report first."));
		return;
	}

	const currency = frappe.boot.sysdefaults.currency;
	const fc = v => format_currency(flt(v), currency);

	const total_po_count = rows.length-1;
	const total_po_value = rows.reduce((s, r) => s + flt(r.po_amount_sar), 0);
	const total_invoiced = rows.reduce((s, r) => s + flt(r.total_invoice_with_vat), 0);
	const total_paid = rows.reduce((s, r) => s + flt(r.paid_amount), 0);
	const total_outstanding = rows.reduce((s, r) => s + flt(r.outstanding_amount), 0);
	const total_yet_to_invoice = rows.reduce((s, r) => s + flt(r.yet_to_be_invoiced), 0);

	const fully_paid = rows.filter(r => r.status === "Fully Paid");
	const partially_paid = rows.filter(r => r.status === "Partially Paid");
	const not_paid = rows.filter(r => r.status === "Not Paid");

	const payment_rate = total_po_value ? Math.min((total_paid / total_po_value) * 100, 100) : 0;
	const fully_pct = total_po_count ? (fully_paid.length / total_po_count) * 100 : 0;
	const partial_pct = total_po_count ? (partially_paid.length / total_po_count) * 100 : 0;
	const not_pct = total_po_count ? (not_paid.length / total_po_count) * 100 : 0;

	const d = new frappe.ui.Dialog({
		title: __("Report KPIs"),
		size: "large",
		fields: [{ fieldtype: "HTML", fieldname: "kpi_html" }]
	});

	d.fields_dict.kpi_html.$wrapper.html(`
		<style>
			.kpi-grid { display:grid; grid-template-columns:repeat(3,1fr); gap:12px; margin-bottom:16px; }
			@media (max-width:700px) { .kpi-grid { grid-template-columns:repeat(2,1fr); } }
			.kpi-card { background:var(--card-bg,#fff); border:1px solid var(--border-color,#d1d8dd);
				border-left:3px solid var(--blue-500,#2490ef); border-radius:8px; padding:12px 14px; }
			.kpi-label { font-size:11px; text-transform:uppercase; letter-spacing:.04em;
				color:var(--text-muted,#8d99a6); margin-bottom:4px; }
			.kpi-value { font-size:17px; font-weight:600; }
			.kpi-card.green  { border-left-color:#28a745; }
			.kpi-card.orange { border-left-color:#fd7e14; }
			.kpi-card.red    { border-left-color:#dc3545; }
			.kpi-stack { height:10px; border-radius:6px; overflow:hidden; display:flex;
				background:var(--gray-200,#e9ecef); margin:10px 0 6px; }
			.kpi-legend { display:flex; gap:16px; font-size:12px; color:var(--text-muted,#8d99a6); flex-wrap:wrap; }
			.kpi-legend span.dot { display:inline-block; width:8px; height:8px; border-radius:50%; margin-right:5px; }
		</style>

		<div class="kpi-grid">
			<div class="kpi-card"><div class="kpi-label">${__("Total POs")}</div><div class="kpi-value">${total_po_count}</div></div>
			<div class="kpi-card"><div class="kpi-label">${__("Total PO Value")}</div><div class="kpi-value">${fc(total_po_value)}</div></div>
			<div class="kpi-card"><div class="kpi-label">${__("Total Invoiced")}</div><div class="kpi-value">${fc(total_invoiced)}</div></div>
			<div class="kpi-card green"><div class="kpi-label">${__("Total Paid")}</div><div class="kpi-value">${fc(total_paid)}</div></div>
			<div class="kpi-card red"><div class="kpi-label">${__("Total Outstanding")}</div><div class="kpi-value">${fc(total_outstanding)}</div></div>
			<div class="kpi-card orange"><div class="kpi-label">${__("Yet to Be Invoiced")}</div><div class="kpi-value">${fc(total_yet_to_invoice)}</div></div>
		</div>

		<div class="kpi-card" style="margin-bottom:14px;">
			<div class="kpi-label">${__("Payment Rate")}</div>
			<div class="kpi-value">${payment_rate.toFixed(1)}%</div>
			<div class="kpi-stack">
				<div style="width:${payment_rate}%;background:#28a745;"></div>
				<div style="width:${100 - payment_rate}%;background:var(--gray-200,#e9ecef);"></div>
			</div>
		</div>

		<div class="kpi-card">
			<div class="kpi-label">${__("PO Status Breakdown")}</div>
			<div class="kpi-stack">
				<div style="width:${fully_pct}%;background:#28a745;"></div>
				<div style="width:${partial_pct}%;background:#fd7e14;"></div>
				<div style="width:${not_pct}%;background:#dc3545;"></div>
			</div>
			<div class="kpi-legend">
				<span><span class="dot" style="background:#28a745;"></span>${__("Fully Paid")}: ${fully_paid.length} (${fully_pct.toFixed(0)}%)</span>
				<span><span class="dot" style="background:#fd7e14;"></span>${__("Partially Paid")}: ${partially_paid.length} (${partial_pct.toFixed(0)}%)</span>
				<span><span class="dot" style="background:#dc3545;"></span>${__("Not Paid")}: ${not_paid.length} (${not_pct.toFixed(0)}%)</span>
			</div>
		</div>

		<div class="text-muted small" style="margin-top:14px;">
			${__("Based on the currently filtered report data ({0} Purchase Orders).", [total_po_count])}
		</div>
	`);

	d.show();
}

// ============================================================================
// PER-ROW "PO SUMMARY" POPUP
// Reuses the same fetch-and-prorate approach as the Purchase Order form
// dialog: PO header + items via frappe.db.get_doc (single permission check,
// no separate child-table query needed), then Receipts / Invoices / Payment
// Entries / Journal Entries via frappe.db.get_list with parent_doctype set
// so the permission check resolves against the parent, not the child table.
// ============================================================================

async function pos_render_dialog(po_name) {
	const d = new frappe.ui.Dialog({
		title: __("Purchase Order Summary — {0}", [po_name]),
		size: "extra-large",
		fields: [{ fieldtype: "HTML", fieldname: "pos_html" }]
	});

	d.show();
	d.fields_dict.pos_html.$wrapper.html(pos_loading_html());

	try {
		const data = await pos_fetch_data(po_name);
		d.fields_dict.pos_html.$wrapper.html(pos_build_html(data));
	} catch (err) {
		console.error("PO Summary error:", err);
		d.fields_dict.pos_html.$wrapper.html(
			`<div class="text-muted text-center" style="padding:60px;">${__("Could not load PO summary. Check console for details.")}</div>`
		);
	}
}

function pos_loading_html() {
	return `
		<div style="text-align:center; padding:80px 0;">
			<div class="spinner" style="width:36px;height:36px;margin:0 auto 12px;
				border:3px solid var(--gray-200,#e9ecef); border-top-color:var(--blue-500,#2490ef);
				border-radius:50%; animation: pos-spin 0.8s linear infinite;"></div>
			<div class="text-muted">${__("Loading PO summary...")}</div>
		</div>
		<style>@keyframes pos-spin { to { transform: rotate(360deg); } }</style>`;
}

function pos_build_share_map(item_rows, po_name) {
	const totals = {};
	const po_amounts = {};
	item_rows.forEach(r => {
		totals[r.parent] = (totals[r.parent] || 0) + flt(r.amount);
		if (r.purchase_order === po_name) {
			po_amounts[r.parent] = (po_amounts[r.parent] || 0) + flt(r.amount);
		}
	});
	const map = {};
	Object.keys(totals).forEach(parent => {
		const total = totals[parent];
		const po_amt = po_amounts[parent] || 0;
		map[parent] = { proportion: total > 0 ? po_amt / total : 1, shared: total > 0 && po_amt < total - 0.01 };
	});
	return map;
}

function pos_compute_po_share(reference_doctype, reference_name, raw_amount, invoice_share, po_name) {
	if (reference_doctype === "Purchase Order" && reference_name === po_name) return raw_amount;
	if (reference_doctype === "Purchase Invoice") {
		const s = invoice_share[reference_name];
		return raw_amount * (s ? s.proportion : 1);
	}
	return 0;
}

async function pos_fetch_data(po_name) {
	const po = await frappe.db.get_doc("Purchase Order", po_name);

	const receipts = await frappe.db.get_list("Purchase Receipt", {
		filters: [
			["Purchase Receipt Item", "purchase_order", "=", po_name],
			["Purchase Receipt", "docstatus", "<", 2]
		],
		fields: ["name", "posting_date", "status", "grand_total", "docstatus"],
		group_by: "name",
		order_by: "posting_date desc",
		limit: 0
	});

	const invoices = await frappe.db.get_list("Purchase Invoice", {
		filters: [
			["Purchase Invoice Item", "purchase_order", "=", po_name],
			["Purchase Invoice", "docstatus", "<", 2]
		],
		fields: ["name", "posting_date", "status", "grand_total", "outstanding_amount", "docstatus"],
		group_by: "name",
		order_by: "posting_date desc",
		limit: 0
	});

	const invoice_names = invoices.map(i => i.name);
	const receipt_names = receipts.map(r => r.name);

	let pi_items = [];
	if (invoice_names.length) {
		pi_items = await frappe.db.get_list("Purchase Invoice Item", {
			filters: { parent: ["in", invoice_names] },
			fields: ["parent", "purchase_order", "amount"],
			parent_doctype: "Purchase Invoice",
			limit: 0
		});
	}
	const invoice_share = pos_build_share_map(pi_items, po_name);

	let pr_items = [];
	if (receipt_names.length) {
		pr_items = await frappe.db.get_list("Purchase Receipt Item", {
			filters: { parent: ["in", receipt_names] },
			fields: ["parent", "purchase_order", "amount"],
			parent_doctype: "Purchase Receipt",
			limit: 0
		});
	}
	const receipt_share = pos_build_share_map(pr_items, po_name);

	const invoices_enriched = invoices.map(inv => {
		const s = invoice_share[inv.name] || { proportion: 1, shared: false };
		return Object.assign({}, inv, {
			shared: s.shared,
			po_share_total: flt(inv.grand_total) * s.proportion,
			po_share_outstanding: flt(inv.outstanding_amount) * s.proportion
		});
	});

	const receipts_enriched = receipts.map(r => {
		const s = receipt_share[r.name] || { proportion: 1, shared: false };
		return Object.assign({}, r, { shared: s.shared, po_share_total: flt(r.grand_total) * s.proportion });
	});

	let pe_refs_invoice = [];
	if (invoice_names.length) {
		pe_refs_invoice = await frappe.db.get_list("Payment Entry Reference", {
			filters: { reference_doctype: "Purchase Invoice", reference_name: ["in", invoice_names] },
			fields: ["parent", "reference_doctype", "reference_name", "allocated_amount"],
			parent_doctype: "Payment Entry",
			limit: 0
		});
	}
	const pe_refs_po = await frappe.db.get_list("Payment Entry Reference", {
		filters: { reference_doctype: "Purchase Order", reference_name: po_name },
		fields: ["parent", "reference_doctype", "reference_name", "allocated_amount"],
		parent_doctype: "Payment Entry",
		limit: 0
	});
	const pe_refs_all = [...pe_refs_invoice, ...pe_refs_po];
	const pe_names = [...new Set(pe_refs_all.map(r => r.parent))];

	let payment_entries = [];
	if (pe_names.length) {
		payment_entries = await frappe.db.get_list("Payment Entry", {
			filters: { name: ["in", pe_names], docstatus: ["<", 2] },
			fields: ["name", "posting_date", "mode_of_payment", "status", "docstatus"],
			order_by: "posting_date desc",
			limit: 0
		});
	}

	const pe_payments = payment_entries.map(p => {
		const refs = pe_refs_all.filter(r => r.parent === p.name);
		const full_allocated = refs.reduce((s, r) => s + flt(r.allocated_amount), 0);
		const po_share = refs.reduce(
			(s, r) => s + pos_compute_po_share(r.reference_doctype, r.reference_name, flt(r.allocated_amount), invoice_share, po_name), 0
		);
		const allocated_to = refs.map(r => (r.reference_name === po_name ? `${r.reference_name} (${__("Advance")})` : r.reference_name)).join(", ");
		return {
			source: "Payment Entry", name: p.name, posting_date: p.posting_date, mode: p.mode_of_payment,
			allocated_to, full_allocated, po_share, status: p.docstatus === 0 ? "Draft" : p.status, docstatus: p.docstatus
		};
	});

	let je_refs_invoice = [];
	if (invoice_names.length) {
		je_refs_invoice = await frappe.db.get_list("Journal Entry Account", {
			filters: { reference_type: "Purchase Invoice", reference_name: ["in", invoice_names] },
			fields: ["parent", "reference_name", "debit_in_account_currency", "credit_in_account_currency"],
			parent_doctype: "Journal Entry",
			limit: 0
		});
	}
	let je_refs_po = await frappe.db.get_list("Journal Entry Account", {
		filters: { reference_type: "Purchase Order", reference_name: po_name },
		fields: ["parent", "reference_name", "debit_in_account_currency", "credit_in_account_currency"],
		parent_doctype: "Journal Entry",
		limit: 0
	});

	je_refs_invoice = je_refs_invoice.map(r => Object.assign({}, r, { reference_doctype: "Purchase Invoice" }));
	je_refs_po = je_refs_po.map(r => Object.assign({}, r, { reference_doctype: "Purchase Order" }));

	const je_refs_all = [...je_refs_invoice, ...je_refs_po]
		.map(r => Object.assign({}, r, { amount: Math.abs(flt(r.debit_in_account_currency) - flt(r.credit_in_account_currency)) }))
		.filter(r => r.amount > 0.001);

	const je_names = [...new Set(je_refs_all.map(r => r.parent))];

	let journal_entries = [];
	if (je_names.length) {
		journal_entries = await frappe.db.get_list("Journal Entry", {
			filters: { name: ["in", je_names], docstatus: ["<", 2] },
			fields: ["name", "posting_date", "voucher_type", "docstatus"],
			order_by: "posting_date desc",
			limit: 0
		});
	}

	const je_payments = journal_entries.map(j => {
		const refs = je_refs_all.filter(r => r.parent === j.name);
		const full_allocated = refs.reduce((s, r) => s + r.amount, 0);
		const po_share = refs.reduce(
			(s, r) => s + pos_compute_po_share(r.reference_doctype, r.reference_name, r.amount, invoice_share, po_name), 0
		);
		const allocated_to = refs.map(r => (r.reference_name === po_name ? `${r.reference_name} (${__("Advance")})` : r.reference_name)).join(", ");
		return {
			source: "Journal Entry", name: j.name, posting_date: j.posting_date, mode: j.voucher_type,
			allocated_to, full_allocated, po_share, status: j.docstatus === 0 ? "Draft" : "Submitted", docstatus: j.docstatus
		};
	});

	const payments = [...pe_payments, ...je_payments].sort((a, b) => (a.posting_date < b.posting_date ? 1 : -1));

	return { po, receipts: receipts_enriched, invoices: invoices_enriched, payments };
}

function pos_build_html(data) {
	const { po, receipts, invoices, payments } = data;
	const currency = po.currency || frappe.boot.sysdefaults.currency;
	const fc = v => format_currency(flt(v), currency);

	const total_paid = payments.filter(p => p.docstatus === 1).reduce((s, p) => s + flt(p.po_share), 0);
	const grand_total = flt(po.grand_total);
	const outstanding = Math.max(grand_total - total_paid, 0);
	const pct_received = flt(po.per_received) || 0;
	const pct_billed = flt(po.per_billed) || 0;
	const pct_paid = grand_total ? Math.min((total_paid / grand_total) * 100, 100) : 0;
	const any_shared = invoices.some(i => i.shared) || receipts.some(r => r.shared);

	return `
	${pos_style_block()}
	<div class="pos-sum">
		<div class="pos-sum-header">
			<div>
				<div class="pos-sum-title">${frappe.utils.escape_html(po.name)}</div>
				<div class="pos-sum-sub">
					${frappe.utils.escape_html(po.supplier_name || po.supplier || "")}
					&nbsp;&middot;&nbsp; ${frappe.datetime.str_to_user(po.transaction_date) || ""}
				</div>
			</div>
			${pos_badge(po.status, "lg")}
		</div>

		<div class="pos-sum-kpis">
			${pos_kpi_card(__("Grand Total"), fc(grand_total), "blue")}
			${pos_kpi_progress(__("Received"), pct_received, "teal")}
			${pos_kpi_progress(__("Billed"), pct_billed, "orange")}
			${pos_kpi_progress(__("Paid"), pct_paid, "green")}
			${pos_kpi_card(__("Outstanding"), fc(outstanding), outstanding > 0 ? "red" : "green")}
		</div>
		${any_shared ? `<div class="pos-sum-note">${__("Some linked documents contain items from other Purchase Orders too — amounts marked")} <span class="pos-shared-tag">${__("Shared")}</span> ${__("are this PO's prorated share, not the full document value.")}</div>` : ""}

		${pos_section(__("PO Items") + ` (${(po.items || []).length})`, pos_items_table(po, fc))}
		${pos_section(__("Purchase Receipts") + ` (${receipts.length})`, receipts.length ? pos_receipts_table(receipts, fc) : pos_empty(__("No Purchase Receipt created against this PO yet.")))}
		${pos_section(__("Purchase Invoices") + ` (${invoices.length})`, invoices.length ? pos_invoices_table(invoices, fc) : pos_empty(__("No Purchase Invoice created against this PO yet.")))}
		${pos_section(__("Payments") + ` (${payments.length})`, payments.length ? pos_payments_table(payments, fc) : pos_empty(__("No payment recorded against this PO or its invoices yet.")))}
	</div>`;
}

function pos_section(title, body) {
	return `<div class="pos-sum-section"><div class="pos-sum-section-title">${title}</div>${body}</div>`;
}

function pos_empty(text) {
	return `<div class="pos-sum-empty">${text}</div>`;
}

function pos_kpi_card(label, value, color) {
	return `<div class="pos-sum-kpi pos-accent-${color}"><div class="pos-sum-kpi-label">${label}</div><div class="pos-sum-kpi-value">${value}</div></div>`;
}

function pos_kpi_progress(label, pct, color) {
	pct = Math.min(Math.max(flt(pct), 0), 100);
	return `<div class="pos-sum-kpi pos-accent-${color}">
		<div class="pos-sum-kpi-label">${label}</div>
		<div class="pos-sum-kpi-value">${pct.toFixed(0)}%</div>
		<div class="pos-sum-progress-track"><div class="pos-sum-progress-fill pos-fill-${color}" style="width:${pct}%;"></div></div>
	</div>`;
}

function pos_badge(status, size) {
	const c = pos_status_color(status);
	const cls = size === "lg" ? "pos-sum-badge pos-sum-badge-lg" : "pos-sum-badge";
	return `<span class="${cls}" style="background:${c.bg};color:${c.fg};">${frappe.utils.escape_html(status || "")}</span>`;
}

function pos_status_color(status) {
	const s = (status || "").toLowerCase();
	if (s.includes("cancel")) return { bg: "#fde2e2", fg: "#c92a2a" };
	if (s.includes("complet") || s.includes("fully") || s === "paid" || s.includes("closed") || s === "submitted") return { bg: "#dff5e3", fg: "#1f9d55" };
	if (s.includes("overdue") || s.includes("unpaid")) return { bg: "#fde2e2", fg: "#c92a2a" };
	if (s.includes("partl") || s.includes("partial") || s.includes("to ") || s.includes("draft")) return { bg: "#fde8cf", fg: "#b15c00" };
	return { bg: "#dceafd", fg: "#1b5fb0" };
}

function pos_fmt_qty(v) {
	v = flt(v);
	return (v % 1 === 0) ? v.toFixed(0) : v.toFixed(2);
}

function pos_shared_tag(is_shared) {
	return is_shared ? `<span class="pos-shared-tag">${__("Shared")}</span>` : "";
}

function pos_items_table(po, fc) {
	const rows = (po.items || []).map(it => {
		const qty = flt(it.qty);
		const received = flt(it.received_qty);
		const billed = flt(it.billed_amt);
		const amount = flt(it.amount);

		let recv_status = "Pending";
		if (received >= qty && qty > 0) recv_status = "Fully Received";
		else if (received > 0) recv_status = "Partially Received";

		let bill_status = "Not Billed";
		if (amount > 0 && billed >= amount - 0.01) bill_status = "Fully Billed";
		else if (billed > 0) bill_status = "Partially Billed";

		return `<tr>
			<td><div class="pos-sum-cell-title">${frappe.utils.escape_html(it.item_code || "")}</div><div class="pos-sum-cell-sub">${frappe.utils.escape_html(it.item_name || "")}</div></td>
			<td class="text-right">${pos_fmt_qty(qty)} ${frappe.utils.escape_html(it.uom || "")}</td>
			<td class="text-right">${pos_fmt_qty(received)}</td>
			<td>${pos_badge(recv_status)}</td>
			<td class="text-right">${fc(billed)}</td>
			<td>${pos_badge(bill_status)}</td>
			<td class="text-right">${fc(it.rate)}</td>
			<td class="text-right pos-sum-cell-strong">${fc(amount)}</td>
		</tr>`;
	}).join("");

	return `<div class="pos-sum-table-wrap"><table class="pos-sum-table">
		<thead><tr><th>${__("Item")}</th><th class="text-right">${__("Ordered")}</th><th class="text-right">${__("Received")}</th>
		<th>${__("Receipt Status")}</th><th class="text-right">${__("Billed")}</th><th>${__("Bill Status")}</th>
		<th class="text-right">${__("Rate")}</th><th class="text-right">${__("Amount")}</th></tr></thead>
		<tbody>${rows}</tbody></table></div>`;
}

function pos_receipts_table(receipts, fc) {
	const rows = receipts.map(r => `<tr>
		<td><a href="/app/purchase-receipt/${encodeURIComponent(r.name)}" target="_blank">${r.name}</a> ${pos_shared_tag(r.shared)}</td>
		<td>${frappe.datetime.str_to_user(r.posting_date) || ""}</td>
		<td>${pos_badge(r.status)}</td>
		<td class="text-right">${fc(r.grand_total)}</td>
		<td class="text-right pos-sum-cell-strong">${fc(r.po_share_total)}</td>
	</tr>`).join("");

	return `<div class="pos-sum-table-wrap"><table class="pos-sum-table">
		<thead><tr><th>${__("Purchase Receipt")}</th><th>${__("Date")}</th><th>${__("Status")}</th>
		<th class="text-right">${__("Receipt Total")}</th><th class="text-right">${__("This PO's Share")}</th></tr></thead>
		<tbody>${rows}</tbody></table></div>`;
}

function pos_invoices_table(invoices, fc) {
	const rows = invoices.map(i => `<tr>
		<td><a href="/app/purchase-invoice/${encodeURIComponent(i.name)}" target="_blank">${i.name}</a> ${pos_shared_tag(i.shared)}</td>
		<td>${frappe.datetime.str_to_user(i.posting_date) || ""}</td>
		<td>${pos_badge(i.status)}</td>
		<td class="text-right">${fc(i.grand_total)}</td>
		<td class="text-right pos-sum-cell-strong">${fc(i.po_share_total)}</td>
		<td class="text-right" style="color:${flt(i.po_share_outstanding) > 0 ? '#c92a2a' : '#1f9d55'};">${fc(i.po_share_outstanding)}</td>
	</tr>`).join("");

	return `<div class="pos-sum-table-wrap"><table class="pos-sum-table">
		<thead><tr><th>${__("Purchase Invoice")}</th><th>${__("Date")}</th><th>${__("Status")}</th>
		<th class="text-right">${__("Invoice Total")}</th><th class="text-right">${__("This PO's Share")}</th><th class="text-right">${__("Outstanding (Est.)")}</th></tr></thead>
		<tbody>${rows}</tbody></table></div>`;
}

function pos_payments_table(payments, fc) {
	const rows = payments.map(p => {
		const link = p.source === "Payment Entry" ? `/app/payment-entry/${encodeURIComponent(p.name)}` : `/app/journal-entry/${encodeURIComponent(p.name)}`;
		const differs = Math.abs(flt(p.full_allocated) - flt(p.po_share)) > 0.01;
		return `<tr>
			<td><a href="${link}" target="_blank">${p.name}</a></td>
			<td><span class="pos-source-tag">${frappe.utils.escape_html(p.source)}</span></td>
			<td>${frappe.datetime.str_to_user(p.posting_date) || ""}</td>
			<td>${frappe.utils.escape_html(p.mode || "-")}</td>
			<td>${frappe.utils.escape_html(p.allocated_to || "-")}</td>
			<td>${pos_badge(p.status)}</td>
			<td class="text-right${differs ? ' pos-prorated' : ''}" title="${differs ? __('Full reference amount: {0}', [fc(p.full_allocated)]) : ''}">${fc(p.po_share)}</td>
		</tr>`;
	}).join("");

	return `<div class="pos-sum-table-wrap"><table class="pos-sum-table">
		<thead><tr><th>${__("Voucher")}</th><th>${__("Source")}</th><th>${__("Date")}</th><th>${__("Mode / Type")}</th>
		<th>${__("Allocated To")}</th><th>${__("Status")}</th><th class="text-right">${__("This PO's Share")}</th></tr></thead>
		<tbody>${rows}</tbody></table></div>`;
}

function pos_style_block() {
	return `<style>
		.pos-sum { font-size: 13px; color: var(--text-color, #1a1a1a); }
		.pos-sum-header { display:flex; align-items:flex-start; justify-content:space-between; padding-bottom:14px; margin-bottom:16px; border-bottom:1px solid var(--border-color,#d1d8dd); }
		.pos-sum-title { font-size:18px; font-weight:600; }
		.pos-sum-sub { color: var(--text-muted,#8d99a6); margin-top:2px; }
		.pos-sum-kpis { display:grid; grid-template-columns:repeat(5,1fr); gap:12px; margin-bottom:10px; }
		@media (max-width:900px) { .pos-sum-kpis { grid-template-columns:repeat(2,1fr); } }
		.pos-sum-kpi { background:var(--card-bg,#fff); border:1px solid var(--border-color,#d1d8dd); border-left:3px solid #2490ef; border-radius:8px; padding:12px 14px; }
		.pos-accent-blue { border-left-color:#2490ef; } .pos-accent-teal { border-left-color:#17a2b8; }
		.pos-accent-orange { border-left-color:#ffa00a; } .pos-accent-green { border-left-color:#28a745; } .pos-accent-red { border-left-color:#dc3545; }
		.pos-sum-kpi-label { font-size:11px; text-transform:uppercase; letter-spacing:.04em; color:var(--text-muted,#8d99a6); margin-bottom:4px; }
		.pos-sum-kpi-value { font-size:17px; font-weight:600; }
		.pos-sum-progress-track { margin-top:8px; height:6px; border-radius:4px; background:var(--gray-200,#e9ecef); overflow:hidden; }
		.pos-sum-progress-fill { height:100%; border-radius:4px; }
		.pos-fill-teal{background:#17a2b8;} .pos-fill-orange{background:#ffa00a;} .pos-fill-green{background:#28a745;}
		.pos-sum-note { font-size:12px; color:var(--text-muted,#8d99a6); margin-bottom:18px; padding:6px 0; }
		.pos-shared-tag, .pos-source-tag { display:inline-block; font-size:10px; font-weight:600; text-transform:uppercase; letter-spacing:.03em; padding:1px 6px; border-radius:8px; margin-left:6px; background:#fde8cf; color:#b15c00; }
		.pos-source-tag { margin-left:0; background:var(--gray-200,#e9ecef); color:var(--text-muted,#8d99a6); }
		.pos-prorated { font-weight:600; border-bottom:1px dashed #ffa00a; cursor:help; }
		.pos-sum-section { margin-bottom:22px; }
		.pos-sum-section-title { font-size:13px; font-weight:600; text-transform:uppercase; letter-spacing:.03em; color:var(--text-muted,#8d99a6); margin-bottom:8px; }
		.pos-sum-table-wrap { border:1px solid var(--border-color,#d1d8dd); border-radius:8px; overflow:hidden; overflow-x:auto; }
		.pos-sum-table { width:100%; border-collapse:collapse; }
		.pos-sum-table th { text-align:left; font-size:11px; text-transform:uppercase; letter-spacing:.03em; color:var(--text-muted,#8d99a6); background:var(--gray-50,#f7f8fa); padding:8px 10px; border-bottom:1px solid var(--border-color,#d1d8dd); white-space:nowrap; }
		.pos-sum-table td { padding:8px 10px; border-bottom:1px solid var(--gray-100,#f1f1f1); vertical-align:middle; }
		.pos-sum-table tr:last-child td { border-bottom:none; }
		.pos-sum-table tr:hover td { background:var(--gray-50,#f7f8fa); }
		.text-right { text-align:right; }
		.pos-sum-cell-title { font-weight:500; } .pos-sum-cell-sub { font-size:11px; color:var(--text-muted,#8d99a6); } .pos-sum-cell-strong { font-weight:600; }
		.pos-sum-badge { display:inline-block; padding:2px 8px; border-radius:10px; font-size:11px; font-weight:500; white-space:nowrap; }
		.pos-sum-badge-lg { padding:4px 12px; font-size:12px; border-radius:12px; }
		.pos-sum-empty { text-align:center; padding:24px; color:var(--text-muted,#8d99a6); border:1px dashed var(--border-color,#d1d8dd); border-radius:8px; }
	</style>`;
}