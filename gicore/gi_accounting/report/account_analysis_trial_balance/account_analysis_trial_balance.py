# -*- coding: utf-8 -*-
# Copyright (c) 2026, HM and contributors
# For license information, please see license.txt
"""
Default behaviour (Group by Account Analysis OFF, Consolidated OFF) now
delegates straight to erpnext.accounts.report.trial_balance so the output
is byte-for-byte identical to the stock ERPNext Trial Balance - same
columns, same tree, same % of account, same fiscal-year / period-closing
handling. Account Analysis grouping and multi-company consolidation are
opt-in extras layered on top, not a replacement.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.trial_balance.trial_balance import execute as erpnext_trial_balance_execute

from gicore.gi_accounting.utils import (
	consolidation_key,
	get_account_analysis_map,
	get_accounts,
	get_analysis_nodes,
	get_companies,
	get_gl_summary,
)

# filters that belong to this app, not to core ERPNext - always stripped
# before delegating to the core report
CUSTOM_FILTER_KEYS = ("account_analysis", "group_by_account_analysis", "consolidated", "companies")


def execute(filters=None):
	filters = frappe._dict(filters or {})

	if filters.get("group_by_account_analysis"):
		return execute_grouped_by_analysis(filters)

	if filters.get("consolidated"):
		return execute_consolidated(filters)

	# ---- default: identical to core ERPNext Trial Balance ----
	core_filters = frappe._dict({k: v for k, v in filters.items() if k not in CUSTOM_FILTER_KEYS})
	return erpnext_trial_balance_execute(core_filters)


# ---------------------------------------------------------------------
# Add-on 1: multi-company consolidation (core report is single-company
# only, so this stays custom)
# ---------------------------------------------------------------------
def execute_consolidated(filters):
	companies = get_companies(filters)
	accounts = get_accounts(companies)

	if filters.get("account_analysis"):
		analysis_map = get_account_analysis_map(companies, filters.get("account_analysis"))
		tagged = set(analysis_map.keys())
		accounts = [a for a in accounts if a.name in tagged]

	account_names = [a.name for a in accounts]
	gl_summary = get_gl_summary(
		companies, filters.from_date, filters.to_date, account_names,
		cost_center=filters.get("cost_center"), finance_book=filters.get("finance_book"),
	)
	show_zero = bool(filters.get("show_zero_values"))
	data = build_consolidated_account_rows(accounts, gl_summary, show_zero)
	return get_columns(), data


# ---------------------------------------------------------------------
# Add-on 2: group by Account Analysis tree (works single-company or
# consolidated - controlled by the same "consolidated" checkbox)
# ---------------------------------------------------------------------
def execute_grouped_by_analysis(filters):
	if not filters.get("from_date") or not filters.get("to_date"):
		frappe.throw(_("Please select From Date and To Date"))
	if not frappe.db.exists("DocType", "Account Analysis"):
		frappe.throw(_("Account Analysis doctype not found on this site"))

	companies = get_companies(filters)
	accounts = get_accounts(companies)

	analysis_map = get_account_analysis_map(companies, filters.get("account_analysis"))
	tagged = set(analysis_map.keys())
	accounts = [a for a in accounts if a.name in tagged]

	account_names = [a.name for a in accounts]
	gl_summary = get_gl_summary(
		companies, filters.from_date, filters.to_date, account_names,
		cost_center=filters.get("cost_center"), finance_book=filters.get("finance_book"),
	)
	show_zero = bool(filters.get("show_zero_values"))
	data = build_analysis_grouped_rows(filters, accounts, analysis_map, gl_summary, show_zero)
	return get_columns(), data


def get_columns():
	return [
		{"label": _("Account / Account Analysis"), "fieldname": "account", "fieldtype": "Data", "width": 340},
		{"label": _("Account Number"), "fieldname": "account_number", "fieldtype": "Data", "width": 100},
		{"label": _("Company"), "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 140},
		{"label": _("Opening Balance"), "fieldname": "opening_balance", "fieldtype": "Currency", "width": 130},
		{"label": _("Debit"), "fieldname": "debit", "fieldtype": "Currency", "width": 130},
		{"label": _("Credit"), "fieldname": "credit", "fieldtype": "Currency", "width": 130},
		{"label": _("Closing Balance"), "fieldname": "closing_balance", "fieldtype": "Currency", "width": 130},
	]


def _row(id_, parent, label, level, values=None, is_group=False, bold=False, account_number=None, company=None):
	# NOTE: "account" holds the raw unique id (matches core ERPNext's own
	# convention of using the real Account name here) so that name_field/
	# parent_field tree-matching in the .js works for collapse/expand.
	# Visual indentation is driven by the "indent" field, not by manual
	# padding, to stay consistent with core's own financial statement
	# reports.
	return {
		"account": id_,
		"parent_account": parent,
		"indent": level,
		"account_number": account_number or "",
		"company": company or "",
		"opening_balance": flt(values.get("opening_balance")) if values else 0.0,
		"debit": flt(values.get("debit")) if values else 0.0,
		"credit": flt(values.get("credit")) if values else 0.0,
		"closing_balance": flt(values.get("closing_balance")) if values else 0.0,
		"bold": bold,
		"is_group": 1 if is_group else 0,
	}


def build_consolidated_account_rows(accounts, gl_summary, show_zero):
	merged = {}
	for a in accounts:
		if a.is_group:
			continue
		key = consolidation_key(a)
		vals = gl_summary.get(a.name, {})
		bucket = merged.setdefault(key, {
			"label": f"{a.account_number} - {a.account_name}" if a.account_number else a.account_name,
			"opening_balance": 0.0, "debit": 0.0, "credit": 0.0, "closing_balance": 0.0,
		})
		for f in ("opening_balance", "debit", "credit", "closing_balance"):
			bucket[f] += flt(vals.get(f))

	rows = []
	for key in sorted(merged.keys()):
		b = merged[key]
		if not show_zero and not any(flt(b[f]) for f in ("opening_balance", "debit", "credit")):
			continue
		rows.append(_row(key, None, b["label"], 0, b, account_number=key, company=_("Consolidated")))
	return rows


def build_analysis_grouped_rows(filters, accounts, analysis_map, gl_summary, show_zero):
	nodes = get_analysis_nodes(filters.get("account_analysis"))
	if not nodes:
		frappe.throw(_("No Account Analysis records found in the selected scope"))

	node_by_name = {n.name: n for n in nodes}
	node_children = {}
	node_roots = []
	for n in nodes:
		if n.parent and n.parent in node_by_name:
			node_children.setdefault(n.parent, []).append(n)
		else:
			node_roots.append(n)

	consolidated = bool(filters.get("consolidated"))
	accounts_by_analysis = {}
	consolidated_buckets = {}

	for acc in accounts:
		if acc.is_group:
			continue
		tags = analysis_map.get(acc.name)
		if not tags:
			continue
		vals = gl_summary.get(acc.name, {})
		for tag in tags:
			if consolidated:
				key = consolidation_key(acc)
				bucket = consolidated_buckets.setdefault((tag, key), {
					"label": f"{acc.account_number} - {acc.account_name}" if acc.account_number else acc.account_name,
					"opening_balance": 0.0, "debit": 0.0, "credit": 0.0, "closing_balance": 0.0,
					"id": f"{tag}::{key}",
				})
				for f in ("opening_balance", "debit", "credit", "closing_balance"):
					bucket[f] += flt(vals.get(f))
			else:
				accounts_by_analysis.setdefault(tag, []).append((acc, vals))

	if consolidated:
		for (tag, key), bucket in consolidated_buckets.items():
			accounts_by_analysis.setdefault(tag, []).append((bucket, None))

	rows = []

	def walk(node, level):
		totals = {"opening_balance": 0.0, "debit": 0.0, "credit": 0.0, "closing_balance": 0.0}
		start_idx = len(rows)

		for kid in sorted(node_children.get(node.name, []), key=lambda x: x.lft):
			kid_row = walk(kid, level + 1)
			if kid_row:
				for f in totals:
					totals[f] += kid_row[f]

		for acc_or_bucket, vals in accounts_by_analysis.get(node.name, []):
			if vals is None:
				b = acc_or_bucket
				if not show_zero and not any(flt(b[f]) for f in ("opening_balance", "debit", "credit")):
					continue
				rows.append(_row(b["id"], node.name, b["label"], level + 1, b, company=_("Consolidated")))
				for f in totals:
					totals[f] += flt(b[f])
			else:
				acc = acc_or_bucket
				if not show_zero and not any(flt(vals.get(f)) for f in ("opening_balance", "debit", "credit")):
					continue
				rows.append(_row(acc.name, node.name, acc.account_name, level + 1, vals,
				                  account_number=acc.account_number, company=acc.company))
				for f in totals:
					totals[f] += flt(vals.get(f))

		if start_idx == len(rows) and not show_zero:
			return None

		row = _row(node.name, node.parent, node.name, level, totals, is_group=True, bold=True)
		rows.insert(start_idx, row)
		return row

	for r in sorted(node_roots, key=lambda x: x.lft):
		walk(r, 0)

	return rows
