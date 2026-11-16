app_name = "gicore"
app_title = "GI Core"
app_publisher = "GI Aqua Tech"
app_description = "GI Core"
app_email = "h.baset@giaquatech.sa"
app_license = "mit"



app_include_js = [
    # "custom_notifications.js",
    "/assets/gicore/js/report_issue_v2.js",
    "/assets/gicore/js/vision_mission_banner.js",
    "/assets/gicore/js/lib/xlsx.full.min.js",
    "/assets/gicore/js/attachment_preview.js",
    # "/assets/gicore/js/account_tree.js",
    # "/assets/gicore/js/navbar_greeting.js",
    "/assets/gicore/js/equipment_dialog.js"
    # "/assets/gicore/js/lib/html2canvas.min.js",
    # "/assets/gicore/js/report_issue_widget.js"
    # other js files...
]

override_doctype_class = {
    "Payroll Entry": "gicore.gi_hr.override.payroll_entry_override.CustomPayrollEntry"
}

app_include_css = [
    "/assets/gicore/css/vision_mission_banner.css",
    # "/assets/gicore/css/navbar_greeting.css",
     "/assets/gicore/css/equipment.css"
]

doc_events = {
    "Equipment Incident": {
        "on_update": "gicore.gi_assets.incident_status.sync",
        "on_cancel": "gicore.gi_assets.incident_status.sync",
    }
}