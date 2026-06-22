frappe.query_reports["User Activity Tracker"] = {
    filters: [
        {
            fieldname: "doctype",
            label: __("DocType"),
            fieldtype: "Link",
            options: "DocType",
            width: "200px"
        },
        {
            fieldname: "user",
            label: __("User"),
            fieldtype: "Link",
            options: "User",
            width: "200px"
        },
        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.nowdate(), -1),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date",
            default: frappe.datetime.nowdate(),
            reqd: 1
        }
    ],

    // Highlight rows with high total activity
    formatter(value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "total" && data && data.total > 20) {
            value = `<b style="color: var(--green-600)">${value}</b>`;
        }
        if (column.fieldname === "submitted_not_creator" && data && data.submitted_not_creator > 0) {
            value = `<span style="color: var(--orange-500)">${value}</span>`;
        }
        return value;
    }
};