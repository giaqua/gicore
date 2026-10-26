frappe.query_reports["User Workflow"] = {
    filters: [
        { fieldname: "user", label: __("User"), fieldtype: "Link", options: "User" },
        { fieldname: "document_type", label: __("DocType"), fieldtype: "Link", options: "DocType" },
        { fieldname: "workflow", label: __("Workflow"), fieldtype: "Link", options: "Workflow" },
        { fieldname: "role", label: __("Role"), fieldtype: "Link", options: "Role" },
        { fieldname: "include_inactive", label: __("Include Inactive Workflows"), fieldtype: "Check" },
    ],
};