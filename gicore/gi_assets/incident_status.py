"""Equipment Incident -> updates Equipment status (v2, self-diagnosing).

If it cannot do its job it shows an orange message on the incident telling you why
(no Equipment link found / incident type not recognised / status option missing).
Edit the lists below to match your own words (English or Arabic).
"""
import frappe

LOST_KEYWORDS = ("lost", "stolen", "theft", "missing", "فقد", "ضياع", "سرق", "مفقود")
REPAIR_KEYWORDS = ("damage", "broken", "fault", "defect", "repair", "malfunction", "maintenance",
                   "تلف", "عطل", "كسر", "صيانة", "تالف", "خراب")
RESOLVED_STATUSES = ("resolved", "closed", "repaired", "completed", "done", "تم الحل", "مغلق", "مكتمل")

# status names to look for in your Equipment "status" options (first match wins)
LOST_OPTIONS = ("Lost", "Missing", "Stolen", "مفقود")
REPAIR_OPTIONS = ("In Repair", "Under Repair", "Under Maintenance", "Damaged", "Maintenance", "في الصيانة", "تالف")
HOLDER_OPTIONS = ("Issued", "In Use", "Assigned", "Custody", "مسلم")
FREE_OPTIONS = ("Available", "In Stock", "متاح")


def _status_options():
	df = frappe.get_meta("Equipment").get_field("status")
	return [o.strip() for o in (df.options or "").split("\n") if o.strip()] if df else []


def _pick(wanted, options):
	for w in wanted:
		if w in options:
			return w
	return None


def _incident_text(doc, meta):
	vals = []
	for df in meta.fields:
		if df.fieldtype in ("Select", "Link", "Data", "Small Text", "Text") and doc.get(df.fieldname):
			label = (df.label or df.fieldname).lower()
			if any(k in label or k in df.fieldname for k in ("type", "category", "nature", "reason", "title", "subject", "description", "نوع")):
				vals.append(str(doc.get(df.fieldname)))
	return " ".join(vals).lower()


def _equipment_names(doc, meta):
	names, found_field = [], False
	for df in meta.fields:
		if df.fieldtype in ("Link", "Dynamic Link"):
			if df.fieldtype == "Link" and df.options == "Equipment":
				found_field = True
				if doc.get(df.fieldname):
					names.append(doc.get(df.fieldname))
			elif df.fieldtype == "Dynamic Link" and doc.get(df.options) == "Equipment":
				found_field = True
				if doc.get(df.fieldname):
					names.append(doc.get(df.fieldname))
		elif df.fieldtype == "Table":
			cmeta = frappe.get_meta(df.options)
			for cdf in cmeta.fields:
				if cdf.fieldtype == "Link" and cdf.options == "Equipment":
					found_field = True
					for row in doc.get(df.fieldname) or []:
						if row.get(cdf.fieldname):
							names.append(row.get(cdf.fieldname))
	return list(dict.fromkeys(names)), found_field


def _holder_status(eq, options):
	has_holder = frappe.db.get_value("Equipment", eq, "current_holder")
	return (_pick(HOLDER_OPTIONS, options) if has_holder else None) or _pick(FREE_OPTIONS, options)


def _set(eq, status, doc, note):
	if not status or not frappe.db.exists("Equipment", eq):
		return False
	old = frappe.db.get_value("Equipment", eq, "status")
	if old == status:
		return False
	frappe.db.set_value("Equipment", eq, "status", status)
	try:
		frappe.get_doc("Equipment", eq).add_comment("Info", f"Status {old} → {status} by {doc.doctype} {doc.name}{note}")
	except Exception:
		pass
	frappe.msgprint(f"Equipment {eq}: status {old} → <b>{status}</b>", indicator="green", alert=True)
	return True


def sync(doc, method=None):
	meta = frappe.get_meta(doc.doctype)
	if method == "on_update" and meta.is_submittable:
		return
	options = _status_options()
	equipment, found_field = _equipment_names(doc, meta)
	if not equipment:
		frappe.msgprint(
			"Equipment status was NOT updated: " + ("the Equipment field is empty." if found_field
			else "no link field to the Equipment doctype was found in this incident."),
			indicator="orange", alert=True)
		return

	if method == "on_cancel":
		for eq in equipment:
			if frappe.db.get_value("Equipment", eq, "status") in (LOST_OPTIONS + REPAIR_OPTIONS):
				_set(eq, _holder_status(eq, options), doc, " (cancelled)")
		return

	state = str(doc.get("status") or doc.get("workflow_state") or "").strip().lower()
	if state in RESOLVED_STATUSES:
		for eq in equipment:
			if frappe.db.get_value("Equipment", eq, "status") in REPAIR_OPTIONS:
				_set(eq, _holder_status(eq, options), doc, " (resolved)")
		return

	text = _incident_text(doc, meta)
	if any(k in text for k in LOST_KEYWORDS):
		target = _pick(LOST_OPTIONS, options)
		label = "Lost"
	elif any(k in text for k in REPAIR_KEYWORDS):
		target = _pick(REPAIR_OPTIONS, options)
		label = "In Repair"
	else:
		frappe.msgprint(f"Equipment status was NOT updated: incident type not recognised (read: “{text or 'empty'}”). "
			"Add your words to LOST_KEYWORDS / REPAIR_KEYWORDS in incident_status.py.", indicator="orange", alert=True)
		return
	if not target:
		frappe.msgprint(f"Equipment status was NOT updated: Equipment 'status' has no option like “{label}”. "
			f"Options are: {', '.join(options)}", indicator="orange", alert=True)
		return
	for eq in equipment:
		_set(eq, target, doc, "")