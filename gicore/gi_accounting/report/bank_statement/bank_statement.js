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
            fieldname: "voucher_no",
            label: "Voucher No",
            fieldtype: "Data"
        }
    ],

    "formatter": function (value, row, column, data, default_formatter) {
        value = default_formatter(value, row, column, data);
        if (data && data.bold) {
            value = "<b>" + value + "</b>";
        }
        return value;
    }
};