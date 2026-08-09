import frappe
from frappe.utils import format_datetime, time_diff_in_seconds, format_duration

@frappe.whitelist()
def get_workflow_timeline(doctype, name):
    versions = frappe.get_all(
        "Version",
        filters={"ref_doctype": doctype, "docname": name},
        fields=["name", "owner", "creation", "data"],
        order_by="creation asc"
    )

    timeline = []
    prev_time = None

    for v in versions:
        data = frappe.parse_json(v.data)
        for change in (data.get("changed") or []):
            if change[0] == "workflow_state":
                cur_time = v.creation
                duration = "-"
                if prev_time:
                    duration = format_duration(time_diff_in_seconds(cur_time, prev_time))
                timeline.append({
                    "state": change[2],
                    "user": v.owner,
                    "time": format_datetime(cur_time),
                    "duration": duration
                })
                prev_time = cur_time

    return timeline