# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT
"""Row-level security: plain employees only see their own custody records.

IT / HR / managers (see utils.PRIVILEGED_ROLES) see everything.
"""

import frappe

from gicore.gi_assets.utils import get_session_employee, is_privileged


def _query(doctype, columns, user=None, include_manager=False):
	user = user or frappe.session.user
	if is_privileged(user):
		return ""

	employee = get_session_employee(user)
	parts = []
	if employee:
		parts += [f"`tab{doctype}`.`{c}` = {frappe.db.escape(employee)}" for c in columns]
	if include_manager:
		parts.append(f"`tab{doctype}`.`manager_user` = {frappe.db.escape(user)}")
	return "(" + " or ".join(parts) + ")" if parts else "1=0"


def _has_permission(doc, columns, user=None, include_manager=False):
	user = user or frappe.session.user
	if is_privileged(user):
		return None

	# brand-new documents (e.g. an employee raising a request) are not restricted here
	is_new = doc.is_new() if hasattr(doc, "is_new") else not doc.get("name")
	if is_new:
		return None

	employee = get_session_employee(user)
	if employee and any(doc.get(c) == employee for c in columns):
		return None
	if include_manager and doc.get("manager_user") == user:
		return None
	return False


# --- Equipment ---------------------------------------------------------------
def equipment_query(user=None):
	return _query("Equipment", ["current_custodian"], user)


def equipment_has_permission(doc, ptype=None, user=None, **kwargs):
	return _has_permission(doc, ["current_custodian"], user)


# --- Equipment Handover ------------------------------------------------------
def handover_query(user=None):
	return _query("Equipment Handover", ["employee", "from_employee"], user)


def handover_has_permission(doc, ptype=None, user=None, **kwargs):
	return _has_permission(doc, ["employee", "from_employee"], user)


# --- Equipment Request -------------------------------------------------------
def request_query(user=None):
	return _query("Equipment Request", ["employee"], user, include_manager=True)


def request_has_permission(doc, ptype=None, user=None, **kwargs):
	return _has_permission(doc, ["employee"], user, include_manager=True)


# --- Equipment Ledger --------------------------------------------------------
def ledger_query(user=None):
	return _query("Equipment Ledger", ["employee"], user)


def ledger_has_permission(doc, ptype=None, user=None, **kwargs):
	return _has_permission(doc, ["employee"], user)


# --- Equipment Incident ------------------------------------------------------
def incident_query(user=None):
	return _query("Equipment Incident", ["employee"], user)


def incident_has_permission(doc, ptype=None, user=None, **kwargs):
	return _has_permission(doc, ["employee"], user)
