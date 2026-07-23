frappe.query_reports["GI General Ledger"] = {
    "filters": [
        {
            "fieldname": "company",
            "label": __("Company"),
            "fieldtype": "Link",
            "options": "Company",
            "default": frappe.defaults.get_user_default("Company"),
            "reqd": 1
        },
        {
            "fieldname": "from_date",
            "label": __("From Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            "reqd": 1
        },
        {
            "fieldname": "to_date",
            "label": __("To Date"),
            "fieldtype": "Date",
            "default": frappe.datetime.get_today(),
            "reqd": 1
        },
        {
            "fieldname": "account",
            "label": __("Account"),
            "fieldtype": "Link",
            "options": "Account",
            "get_query": function() {
                return {
                    "filters": {
                        "company": frappe.query_report.get_filter_value("company"),
                        "is_group": 0
                    }
                };
            }
        },
        {
            "fieldname": "cost_center",
            "label": __("Cost Center"),
            "fieldtype": "Link",
            "options": "Cost Center"
        },
        {
            "fieldname": "project",
            "label": __("Project"),
            "fieldtype": "Link",
            "options": "Project"
        }
    ],
    
    "onload": function(report) {
        // Add custom print button
        report.page.add_inner_button(__("Print General Ledger"), function() {
            print_general_ledger(report);
        });
    }
};

// Print function
function print_general_ledger(report) {
    // Get current filters
    const filters = report.get_values();
    
    // Validate required filters
    if (!filters.from_date || !filters.to_date) {
        frappe.msgprint(__("Please select From Date and To Date"));
        return;
    }
    
    // Show loading message
    frappe.show_alert({
        message: __("Generating print..."),
        indicator: "green"
    });
    
    // Call backend to get HTML
    frappe.call({
        method: "gicore.gi_accounting.report.gi_general_ledger.gi_general_ledger.get_print_html",
        args: {
            "filters": filters
        },
        callback: function(response) {
            if (response.message) {
                // Open in new window for printing
                const printWindow = window.open("", "_blank");
                printWindow.document.write(response.message);
                printWindow.document.close();
                printWindow.print();
            } else {
                frappe.msgprint(__("No data to print"));
            }
        },
        error: function(error) {
            console.error(error);
            frappe.msgprint({
                title: __("Error"),
                indicator: "red",
                message: __("Failed to generate print. Please check console for details.")
            });
        }
    });
}