// Employee Document Expiry — report filters + row coloring
// Place at: gicore/gi_hr/report/employee_document_expiry/employee_document_expiry.js

frappe.query_reports["Employee Document Expiry"] = {
    filters: [
        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company",
        },
        {
            fieldname: "document_type",
            label: "Document Type",
            fieldtype: "Select",
            options: "\nIqama\nPassport\nWork Permit\nGOSI Card\nDriving License\nHealth Certificate\nVisa\nOther",
        },
        {
            fieldname: "employee",
            label: "Employee",
            fieldtype: "Link",
            options: "Employee",
        },
        {
            fieldname: "status",
            label: "Status",
            fieldtype: "Select",
            options: "All\nExpired\nCritical (<=30d)\nWarning (<=60d)\nUpcoming (<=90d)\nValid",
            default: "All",
        },
    ],

    formatter: (value, row, column, data, default_formatter) => {
        value = default_formatter(value, row, column, data);
        if (column.fieldname === "status") {
            const colors = {
                "Expired": "red",
                "Critical (<=30d)": "orange",
                "Warning (<=60d)": "yellow",
                "Upcoming (<=90d)": "blue",
                "Valid": "green",
            };
            const color = colors[data.status] || "gray";
            value = `<span style="color: ${color}; font-weight: 600;">${data.status}</span>`;
        }
        return value;
    },
};