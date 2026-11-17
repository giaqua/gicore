# Copyright (c) 2026, Hamzah Alshaibani and contributors
# License: MIT
"""Idempotent setup: roles, workflow, print format, workspace.

Everything is created only if it does not exist yet, so re-running (after_migrate)
never overwrites changes the customer made in the UI.
"""

import json

import frappe

ROLES = ["Equipment Manager", "Equipment User", "Equipment Line Manager"]

WORKFLOW_NAME = "Equipment Request Approval"

# (state, doc_status, role allowed to edit in that state, style)
WORKFLOW_STATES = [
	("Draft", "0", "Employee", "Warning"),
	("Pending Manager", "0", "Equipment Line Manager", "Warning"),
	("Pending IT", "0", "Equipment Manager", "Warning"),
	("Approved", "1", "Equipment Manager", "Success"),
	("Fulfilled", "1", "Equipment Manager", "Success"),
	("Rejected", "0", "Equipment Manager", "Danger"),
	("Cancelled", "2", "Equipment Manager", "Danger"),
]

MANAGER_CONDITION = "(not doc.manager_user) or doc.manager_user == frappe.session.user"

# (from state, action, to state, role, condition)
WORKFLOW_TRANSITIONS = [
	("Draft", "Send for Approval", "Pending Manager", "Employee", None),
	("Draft", "Send for Approval", "Pending Manager", "Equipment User", None),
	("Pending Manager", "Approve", "Pending IT", "Equipment Line Manager", MANAGER_CONDITION),
	("Pending Manager", "Reject", "Rejected", "Equipment Line Manager", MANAGER_CONDITION),
	("Pending IT", "Approve", "Approved", "Equipment Manager", None),
	("Pending IT", "Reject", "Rejected", "Equipment Manager", None),
	("Rejected", "Reopen", "Draft", "Employee", None),
	("Rejected", "Reopen", "Draft", "Equipment User", None),
	("Approved", "Cancel Request", "Cancelled", "Equipment Manager", None),
]


def after_install():
	ensure_setup()


def after_migrate():
	ensure_setup()


def ensure_setup():
	create_roles()
	backfill_brands_models()
	create_workflow()
	create_print_format()
	create_workspace()
	frappe.db.commit()


def create_roles():
	for role in ROLES:
		if not frappe.db.exists("Role", role):
			frappe.get_doc({"doctype": "Role", "role_name": role, "desk_access": 1}).insert(
				ignore_permissions=True
			)


def backfill_brands_models():
	"""Equipment.brand / model used to be free text. Create the matching master records so that
	units saved before the upgrade keep validating. Idempotent: existing records are left alone."""
	if not (frappe.db.exists("DocType", "Equipment Brand") and frappe.db.exists("DocType", "Equipment Model")):
		return
	try:
		rows = frappe.db.sql(
			"select distinct brand, model from `tabEquipment` where ifnull(brand, '') != '' or ifnull(model, '') != ''",
			as_dict=True,
		)
	except Exception:
		return

	for r in rows:
		brand, model = (r.brand or "").strip(), (r.model or "").strip()
		try:
			if brand and not frappe.db.exists("Equipment Brand", brand):
				frappe.get_doc({"doctype": "Equipment Brand", "brand_name": brand}).insert(ignore_permissions=True)
			if model and brand and not frappe.db.exists("Equipment Model", model):
				frappe.get_doc({"doctype": "Equipment Model", "model_name": model, "brand": brand}).insert(
					ignore_permissions=True
				)
		except Exception:
			frappe.log_error(title="Equipment brand/model backfill failed")


def create_workflow():
	if frappe.db.exists("Workflow", WORKFLOW_NAME):
		return
	if not frappe.db.exists("DocType", "Equipment Request"):
		return

	for state, _doc_status, _role, style in WORKFLOW_STATES:
		if not frappe.db.exists("Workflow State", state):
			frappe.get_doc(
				{"doctype": "Workflow State", "workflow_state_name": state, "style": style}
			).insert(ignore_permissions=True)

	for action in sorted({t[1] for t in WORKFLOW_TRANSITIONS}):
		if not frappe.db.exists("Workflow Action Master", action):
			frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": action}).insert(
				ignore_permissions=True
			)

	wf = frappe.get_doc(
		{
			"doctype": "Workflow",
			"workflow_name": WORKFLOW_NAME,
			"document_type": "Equipment Request",
			"workflow_state_field": "workflow_state",
			"is_active": 1,
			"send_email_alert": 0,
			"states": [
				{"state": state, "doc_status": doc_status, "allow_edit": role}
				for state, doc_status, role, _style in WORKFLOW_STATES
			],
			"transitions": [
				{
					"state": src,
					"action": action,
					"next_state": dst,
					"allowed": role,
					"allow_self_approval": 1,
					"condition": condition,
				}
				for src, action, dst, role, condition in WORKFLOW_TRANSITIONS
			],
		}
	)
	wf.insert(ignore_permissions=True)


def create_print_format():
	name = "Equipment Handover Form"
	if frappe.db.exists("Print Format", name):
		return
	if not frappe.db.exists("DocType", "Equipment Handover"):
		return

	path = frappe.get_app_path("gicore", "gi_assets", "print_format", "equipment_handover_form.html")
	with open(path, encoding="utf-8") as f:
		html = f.read()

	frappe.get_doc(
		{
			"doctype": "Print Format",
			"name": name,
			"doc_type": "Equipment Handover",
			"module": "GI Assets",
			"standard": "No",
			"custom_format": 1,
			"print_format_type": "Jinja",
			"html": html,
		}
	).insert(ignore_permissions=True)

	# make it the default print format
	frappe.make_property_setter(
		{
			"doctype": "Equipment Handover",
			"doctype_or_field": "DocType",
			"property": "default_print_format",
			"value": name,
			"property_type": "Data",
		}
	)


def create_workspace():
	"""Nice landing page. Non-critical: never block install if the Workspace schema differs."""
	if frappe.db.exists("Workspace", "GI Assets"):
		return
	try:
		shortcuts = [
			("Equipment Handover", "DocType", "Equipment Handover"),
			("Equipment Request", "DocType", "Equipment Request"),
			("Equipment", "DocType", "Equipment"),
			("Equipment Ledger", "DocType", "Equipment Ledger"),
			("Custody by Employee", "Report", "Custody by Employee"),
			("Equipment Incident", "DocType", "Equipment Incident"),
		]
		cards = {
			"Transactions": [
				("Equipment Handover", "DocType"),
				("Equipment Request", "DocType"),
				("Equipment Stock Entry", "DocType"),
				("Equipment Incident", "DocType"),
			],
			"Masters": [
				("Equipment", "DocType"),
				("Equipment Category", "DocType"),
				("Equipment Brand", "DocType"),
				("Equipment Model", "DocType"),
				("Equipment Kit", "DocType"),
				("Equipment Settings", "DocType"),
			],
			"Reports": [
				("Equipment Ledger", "DocType"),
				("Custody by Employee", "Report"),
				("Equipment Status Summary", "Report"),
				("Warranty Expiry", "Report"),
				("Left Employees With Custody", "Report"),
			],
		}

		content = [
			{
				"id": "eq_header",
				"type": "header",
				"data": {"text": '<span class="h4"><b>GI Assets</b></span>', "col": 12},
			}
		]
		for i, (label, _t, _l) in enumerate(shortcuts):
			content.append(
				{"id": f"eq_sc_{i}", "type": "shortcut", "data": {"shortcut_name": label, "col": 4}}
			)
		for i, card in enumerate(cards):
			content.append({"id": f"eq_card_{i}", "type": "card", "data": {"card_name": card, "col": 4}})

		links = []
		for card, items in cards.items():
			links.append({"type": "Card Break", "label": card, "hidden": 0})
			for label, kind in items:
				links.append(
					{
						"type": "Link",
						"label": label,
						"link_type": kind,
						"link_to": label,
						"is_query_report": 1 if kind == "Report" else 0,
						"onboard": 0,
						"hidden": 0,
					}
				)

		frappe.get_doc(
			{
				"doctype": "Workspace",
				"name": "GI Assets",
				"label": "GI Assets",
				"title": "GI Assets",
				"module": "GI Assets",
				"public": 1,
				"is_hidden": 0,
				"content": json.dumps(content),
				"shortcuts": [
					{
						"label": label,
						"type": kind,
						"link_to": link_to,
						"doc_view": "List" if kind == "DocType" else "",
					}
					for label, kind, link_to in shortcuts
				],
				"links": links,
			}
		).insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="GI Assets workspace creation failed")
