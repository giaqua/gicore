# -*- coding: utf-8 -*-
# Copyright (c) 2026, HM and contributors
# For license information, please see license.txt
"""
Shared engine used by all three reports in this app:
	- Account Analysis Trial Balance
	- Account Analysis Profit and Loss
	- Account Analysis Balance Sheet

ASSUMPTIONS ABOUT YOUR EXISTING "Account Analysis" DOCTYPE
------------------------------------------------------------------
You already have a tree Doctype called "Account Analysis" and a child
table Doctype "Account Analysis Item" (fieldname on Account:
`custom_account_analysis`) linking each Account to one or more
Account Analysis values.

This file assumes the standard Frappe tree-doctype field names:
	- Account Analysis: name, parent_account_analysis, is_group, lft, rgt
	- Account Analysis Item: parent (-> Account), account_analysis (-> Account Analysis)

If your "Account Analysis" doctype uses a different fieldname for the
parent link (Frappe auto-generates it as `parent_<scrubbed_doctype_name>`
when you tick "Is Tree" - check Setup > Customize Form on "Account
Analysis" to confirm), update PARENT_FIELD below to match. Nothing else
in this app needs to change.
"""

import frappe
from frappe import _
from frappe.utils import flt
from frappe.utils.nestedset import get_descendants_of

ANALYSIS_DOCTYPE = "Account Analysis"
PARENT_FIELD = "parent_account_analysis"  # <-- verify against your doctype, see note above


def get_analysis_scope(account_analysis):
	"""Selected node + all its descendants (so filtering by a parent node
	automatically pulls in every account tagged with a child node too)."""
	if not account_analysis:
		return []
	scope = get_descendants_of(ANALYSIS_DOCTYPE, account_analysis, ignore_permissions=True)
	scope.append(account_analysis)
	return scope


def get_account_analysis_map(companies, account_analysis=None):
	"""Return {account_name: [Account Analysis values tagged on it]} for
	accounts belonging to `companies`, optionally restricted to
	`account_analysis` (+ its descendants)."""
	if not companies:
		return {}

	values = {"companies": tuple(companies)}
	analysis_filter_sql = ""

	if account_analysis:
		scope = get_analysis_scope(account_analysis)
		if not scope:
			return {}
		values["analysis_scope"] = tuple(scope)
		analysis_filter_sql = " AND aai.account_analysis IN %(analysis_scope)s"

	rows = frappe.db.sql(
		"""
		SELECT acc.name AS account, aai.account_analysis AS account_analysis
		FROM `tabAccount` acc
		INNER JOIN `tabAccount Analysis Item` aai
			ON aai.parent = acc.name AND aai.parenttype = 'Account'
		WHERE acc.company IN %(companies)s
		{analysis_filter_sql}
		""".format(analysis_filter_sql=analysis_filter_sql),
		values,
		as_dict=True,
	)

	account_map = {}
	for r in rows:
		account_map.setdefault(r.account, []).append(r.account_analysis)
	return account_map


def get_analysis_nodes(account_analysis=None):
	"""Ordered (by lft) list of Account Analysis nodes in scope, as dicts
	with name/parent/is_group/lft/rgt - used to build the grouped tree."""
	values = {}
	where = ""
	if account_analysis:
		scope = get_analysis_scope(account_analysis)
		if not scope:
			return []
		values["scope"] = tuple(scope)
		where = "WHERE name IN %(scope)s"

	return frappe.db.sql(
		"""
		SELECT name, `{parent_field}` AS parent, is_group, lft, rgt
		FROM `tab{doctype}`
		{where}
		ORDER BY lft
		""".format(parent_field=PARENT_FIELD, doctype=ANALYSIS_DOCTYPE, where=where),
		values,
		as_dict=True,
	)


def get_accounts(companies):
	"""All accounts (any company in `companies`) with nested-set fields."""
	return frappe.db.sql(
		"""
		SELECT name, account_name, account_number, parent_account, is_group,
		       root_type, report_type, company, lft, rgt
		FROM `tabAccount`
		WHERE company IN %(companies)s
		ORDER BY company, lft
		""",
		{"companies": tuple(companies)},
		as_dict=True,
	)


def get_gl_summary(companies, from_date, to_date, accounts, cost_center=None, finance_book=None):
	"""Raw-SQL aggregation of GL Entry into opening/period/closing per account.
	Returns {account: {opening_balance, debit, credit, closing_balance}}."""
	summary = {a: {"opening_balance": 0.0, "debit": 0.0, "credit": 0.0, "closing_balance": 0.0} for a in accounts}
	if not accounts:
		return summary

	conditions = ["company IN %(companies)s", "account IN %(accounts)s", "is_cancelled = 0"]
	values = {
		"companies": tuple(companies),
		"accounts": tuple(accounts),
		"from_date": from_date,
		"to_date": to_date,
	}
	if cost_center:
		conditions.append("cost_center = %(cost_center)s")
		values["cost_center"] = cost_center
	if finance_book:
		conditions.append("(finance_book = %(finance_book)s OR finance_book IS NULL OR finance_book = '')")
		values["finance_book"] = finance_book

	base_where = " AND ".join(conditions)

	opening_rows = frappe.db.sql(
		f"""
		SELECT account, SUM(debit) AS debit, SUM(credit) AS credit
		FROM `tabGL Entry`
		WHERE {base_where} AND (posting_date < %(from_date)s OR IFNULL(is_opening, 'No') = 'Yes')
		GROUP BY account
		""",
		values,
		as_dict=True,
	)
	period_rows = frappe.db.sql(
		f"""
		SELECT account, SUM(debit) AS debit, SUM(credit) AS credit
		FROM `tabGL Entry`
		WHERE {base_where} AND posting_date BETWEEN %(from_date)s AND %(to_date)s
			AND IFNULL(is_opening, 'No') = 'No'
		GROUP BY account
		""",
		values,
		as_dict=True,
	)

	for r in opening_rows:
		summary[r.account]["opening_balance"] += flt(r.debit) - flt(r.credit)
	for r in period_rows:
		summary[r.account]["debit"] += flt(r.debit)
		summary[r.account]["credit"] += flt(r.credit)
	for acc, d in summary.items():
		d["closing_balance"] = d["opening_balance"] + d["debit"] - d["credit"]

	return summary


def consolidation_key(account):
	"""Accounts across sibling companies are matched for consolidation by
	account_number (preferred) or, failing that, by account_name. This
	assumes your companies share a common Chart of Accounts template -
	confirm that holds for GI Aqua Tech / TDCO before trusting the totals."""
	return account.account_number or account.account_name


def signed_amount(root_type, debit, credit):
	"""Natural-balance sign convention: Asset/Expense accounts read positive
	on a debit balance; Liability/Equity/Income read positive on a credit
	balance."""
	debit, credit = flt(debit), flt(credit)
	if root_type in ("Asset", "Expense"):
		return debit - credit
	return credit - debit


def get_companies(filters):
	if filters.get("consolidated") and filters.get("companies"):
		companies = filters.companies
		if isinstance(companies, str):
			companies = [c.strip() for c in companies.split(",") if c.strip()]
		return companies
	if not filters.get("company"):
		frappe.throw(_("Please select a Company"))
	return [filters.company]
