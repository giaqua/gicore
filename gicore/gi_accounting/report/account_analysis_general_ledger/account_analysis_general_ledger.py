# -*- coding: utf-8 -*-
# Copyright (c) 2026, HM and contributors
# For license information, please see license.txt
"""
Default behaviour (no Account Analysis filter, Group by Account Analysis
OFF) delegates straight to erpnext.accounts.report.general_ledger - same
columns, same categorize_by options, same everything.

Account Analysis is layered on top as two opt-in extras:
	1. account_analysis filter -> restricts the GL rows to accounts tagged
	   with that node (or its descendants), and adds an "Account Analysis"
	   column so you can see which tag(s) each row's account carries.
	2. group_by_account_analysis checkbox -> re-buckets the (already
	   fetched) GL rows under an Account Analysis subtotal header instead
	   of the core report's own voucher/account/party grouping.

CAVEAT: recomputing a running "balance" column after filtering rows is
only done as a simple per-account cumulative sum (matches core's
"Categorize by Account" mode). If you're using "Categorize by Voucher"
or "Categorize by Party" together with the account_analysis filter, the
balance column on the filtered view may not exactly match what core
would have shown for that grouping - the debit/credit figures themselves
are always correct either way, only the running balance column is the
approximation. Test before relying on it.
"""

import frappe
from frappe import _
from frappe.utils import flt

from erpnext.accounts.report.general_ledger.general_ledger import execute as erpnext_gl_execute

from gicore.gi_accounting.utils import get_account_analysis_map, get_analysis_nodes

CUSTOM_FILTER_KEYS = ("account_analysis", "group_by_account_analysis")
ANALYSIS_COLUMN = {
	"label": _("Account Analysis"),
	"fieldname": "account_analysis",
	"fieldtype": "Data",
	"width": 160,
}


def execute(filters=None):
	filters = frappe._dict(filters or {})

	core_filters = frappe._dict({k: v for k, v in filters.items() if k not in CUSTOM_FILTER_KEYS})
	result = erpnext_gl_execute(core_filters)
	if not result:
		return result

	columns, data = result[0], result[1]
	rest = result[2:] if len(result) > 2 else ()

	if not filters.get("account_analysis") and not filters.get("group_by_account_analysis"):
		return result  # untouched, identical to core

	companies = [core_filters.company] if core_filters.get("company") else []
	analysis_map = get_account_analysis_map(companies, filters.get("account_analysis"))

	if filters.get("account_analysis"):
		tagged = set(analysis_map.keys())
		data = [d for d in data if not d.get("account") or d.get("account") in tagged]
		data = _recompute_running_balance(data)

	columns = list(columns) + [ANALYSIS_COLUMN]
	for d in data:
		acc = d.get("account")
		d["account_analysis"] = ", ".join(analysis_map.get(acc, [])) if acc else ""

	if filters.get("group_by_account_analysis"):
		data = _group_by_analysis(filters, data, analysis_map)

	if rest:
		return (columns, data) + rest
	return columns, data


def _recompute_running_balance(data):
	"""Simple per-account cumulative balance, in existing row order.
	Rows without an 'account' (e.g. opening/closing/total summary rows
	added by core) are left untouched."""
	if not data or "balance" not in data[0]:
		return data

	running = {}
	for d in data:
		acc = d.get("account")
		if not acc:
			continue
		running.setdefault(acc, 0.0)
		running[acc] += flt(d.get("debit")) - flt(d.get("credit"))
		d["balance"] = running[acc]
	return data


def _group_by_analysis(filters, data, analysis_map):
	"""Re-order the already-filtered rows under an Account Analysis
	subtotal header. Rows with no account (core's own opening/closing/
	total rows) are kept at the end, untouched."""
	nodes = get_analysis_nodes(filters.get("account_analysis"))
	order = {n.name: i for i, n in enumerate(nodes)}  # tree (lft) order

	buckets = {}
	unassigned = []
	trailing = []

	for d in data:
		acc = d.get("account")
		if not acc:
			trailing.append(d)
			continue
		tags = analysis_map.get(acc)
		if not tags:
			unassigned.append(d)
			continue
		for tag in tags:
			buckets.setdefault(tag, []).append(d)

	grouped = []
	for tag in sorted(buckets.keys(), key=lambda t: order.get(t, 9999)):
		rows = buckets[tag]
		debit_total = sum(flt(r.get("debit")) for r in rows)
		credit_total = sum(flt(r.get("credit")) for r in rows)
		grouped.append({
			"account": _("Account Analysis: {0}").format(tag),
			"debit": debit_total,
			"credit": credit_total,
			"bold": 1,
			"is_group_header": 1,
		})
		grouped.extend(rows)
		grouped.append({
			"account": _("Subtotal: {0}").format(tag),
			"debit": debit_total,
			"credit": credit_total,
			"bold": 1,
		})

	if unassigned:
		grouped.append({"account": _("Not Tagged with Account Analysis"), "bold": 1, "is_group_header": 1})
		grouped.extend(unassigned)

	grouped.extend(trailing)
	return grouped
