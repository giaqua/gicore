// Copyright (c) 2026
frappe.query_reports["Bank Statement"] = {
    "filters": [
        {
            fieldname: "company",
            label: "Company",
            fieldtype: "Link",
            options: "Company",
            default: frappe.defaults.get_user_default("Company"),
            reqd: 1
        },
        {
            fieldname: "account",
            label: "Bank Account",
            fieldtype: "Link",
            options: "Account",
            reqd: 1,
            get_query: function () {
                var company = frappe.query_report.get_filter_value("company");
                return {
                    filters: {
                        company: company,
                        account_type: ["in", ["Bank", "Cash"]],
                        is_group: 0
                    }
                };
            }
        },
        {
            fieldname: "from_date",
            label: "From Date",
            fieldtype: "Date",
            default: frappe.datetime.add_months(frappe.datetime.get_today(), -1),
            reqd: 1
        },
        {
            fieldname: "to_date",
            label: "To Date",
            fieldtype: "Date",
            default: frappe.datetime.get_today(),
            reqd: 1
        },
        {
            fieldname: "party_type",
            label: "Party Type",
            fieldtype: "Link",
            options: "Party Type"
        },
        {
            fieldname: "party",
            label: "Party",
            fieldtype: "Dynamic Link",
            get_options: function () {
                return frappe.query_report.get_filter_value("party_type");
            }
        },
        {
            fieldname: "voucher_type",
            label: "Voucher Type",
            fieldtype: "Select",
            options: [
                "", "Journal Entry", "Payment Entry", "Sales Invoice",
                "Purchase Invoice", "Expense Claim", "Bank Reconciliation Statement"
            ].join("\n")
        },
        {
            fieldname: "voucher_no",
            label: "Voucher No",
            fieldtype: "Data"
        },
        {
            fieldname: "reference_no",
            label: "Reference No",
            fieldtype: "Data"
        },
        {
            fieldname: "remarks",
            label: "Remarks",
            fieldtype: "Data"
        }
    ],

    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data && data.bold) {
            value = "<b>" + value + "</b>";
        }
        return value;
    },

    "onload": function (report) {
        report.page.add_inner_button(__("Download PDF"), function () {
            var filters = report.get_values();

            if (!filters.account || !filters.company || !filters.from_date || !filters.to_date) {
                frappe.msgprint(__("Please set Company, Bank Account, From Date and To Date before downloading."));
                return;
            }

            var params = $.param(filters);
            var url = frappe.urllib.get_full_url(
                "/api/method/gicore.gi_accounting.report.bank_statement.bank_statement.download_bank_statement_pdf?" + params
            );
            window.open(url);
        });
    }
};