// frappe.provide("gicore.issue");

// // Wait for Frappe desk to be fully loaded
// $(document).on("startup", function () {
//     gicore.issue.add_navbar_button();
// });

// // Fallback if startup already fired
// frappe.ready(function () {
//     setTimeout(() => {
//         if (!$(".report-issue-btn").length) {
//             gicore.issue.add_navbar_button();
//         }
//     }, 1500);
// });

// gicore.issue.add_navbar_button = function () {
//     // Target the Settings (gear icon) dropdown
//     const $settingsMenu = $(".navbar-settings .dropdown-menu");

//     if (!$settingsMenu.length || $(".report-issue-btn").length) return;

//     $settingsMenu.append(`
//         <li class="dropdown-divider"></li>
//         <li class="report-issue-btn">
//             <a class="dropdown-item" href="#" onclick="gicore.issue.show_dialog(); return false;">
//                 <svg class="mr-2" xmlns="http://www.w3.org/2000/svg" width="14" height="14" fill="currentColor" viewBox="0 0 16 16">
//                     <path d="M4.355.522a.5.5 0 0 1 .623.333l.291.956A4.979 4.979 0 0 1 8 1c.88 0 1.712.23 2.43.635l.302-.997a.5.5 0 1 1 .956.29l-.308 1.018A5.014 5.014 0 0 1 13 6h.5a.5.5 0 0 0 .5-.5V5a.5.5 0 0 0 1 0v.5A1.5 1.5 0 0 1 13.5 7H13v1h1.5a.5.5 0 0 1 0 1H13v1h.5a1.5 1.5 0 0 1 1.5 1.5v.5a.5.5 0 0 1-1 0v-.5a.5.5 0 0 0-.5-.5H13a5 5 0 0 1-10 0h-.5a.5.5 0 0 0-.5.5v.5a.5.5 0 0 1-1 0v-.5A1.5 1.5 0 0 1 2.5 11H3v-1H1.5a.5.5 0 0 1 0-1H3V8h-.5A1.5 1.5 0 0 1 1 6.5V5a.5.5 0 0 0 1 0v.5a.5.5 0 0 0 .5.5H3a5.014 5.014 0 0 1 2.018-3.054L4.71.845a.5.5 0 0 1 .333-.623z"/>
//                 </svg>
//                 ${__("Report an Issue")}
//             </a>
//         </li>
//     `);
// };

// gicore.issue.show_dialog = function () {
//     // Close the help dropdown first
//    $(".navbar-settings").removeClass("show");
// $(".navbar-settings .dropdown-menu").removeClass("show");

//     const dialog = new frappe.ui.Dialog({
//         title: __("Report an Issue"),
//         size: "large",
//         fields: [
//             {
//                 fieldtype: "Data",
//                 fieldname: "subject",
//                 label: __("Subject"),
//                 reqd: 1,
//                 placeholder: "Brief description of the issue"
//             },
//             {
//                 fieldtype: "Column Break"
//             },
//             {
//                 fieldtype: "Select",
//                 fieldname: "priority",
//                 label: __("Priority"),
//                 options: ["Low", "Medium", "High", "Urgent"],
//                 default: "Medium"
//             },
//             {
//                 fieldtype: "Section Break"
//             },
//             {
//                 fieldtype: "Text Editor",
//                 fieldname: "description",
//                 label: __("Description"),
//                 reqd: 1,
//                 placeholder: "Please describe the issue in detail..."
//             },
//             {
//                 fieldtype: "Section Break",
//                 label: __("Additional Info")
//             },
//             {
//                 fieldtype: "Data",
//                 fieldname: "raised_by",
//                 label: __("Your Email"),
//                 default: frappe.session.user,
//                 read_only: 1
//             },
//             {
//                 fieldtype: "Column Break"
//             },
//             {
//                 fieldtype: "Data",
//                 fieldname: "current_page",
//                 label: __("Current Page"),
//                 default: window.location.href,
//                 read_only: 1
//             }
//         ],
//         primary_action_label: __("Submit Issue"),
//         primary_action(values) {
//             dialog.disable_primary_action();

//             frappe.call({
//                 method: "frappe.client.insert",
//                 args: {
//                     doc: {
//                         doctype: "Issue",
//                         subject: values.subject,
//                         description: values.description,
//                         priority: values.priority,
//                         raised_by: values.raised_by,
//                         // store current page in a custom field if you have one:
//                         // custom_page_url: values.current_page
//                     }
//                 },
//                 callback(r) {
//                     if (r.message) {
//                         dialog.hide();
//                         frappe.show_alert({
//                             message: __(`Issue #{0} submitted successfully!`, [r.message.name]),
//                             indicator: "green"
//                         }, 5);
//                     }
//                 },
//                 error() {
//                     dialog.enable_primary_action();
//                     frappe.show_alert({
//                         message: __("Failed to submit issue. Please try again."),
//                         indicator: "red"
//                     }, 5);
//                 }
//             });
//         }
//     });

//     dialog.show();
// };

// gicore/public/js/report_issue_widget.js

frappe.after_ajax(() => {
    if (document.getElementById('report-issue-fab')) return;

    // Floating button
    const fab = document.createElement('div');
    fab.id = 'report-issue-fab';
    fab.innerHTML = `<i class="fa fa-exclamation-circle"></i> Report an Issue`;
    fab.style.cssText = `
        position: fixed;
        bottom: 20px;
        right: 20px;
        background: #D50000;
        color: white;
        padding: 10px 16px;
        border-radius: 24px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.25);
        cursor: pointer;
        z-index: 9999;
        font-size: 13px;
        font-weight: 500;
        display: flex;
        align-items: center;
        gap: 6px;
        transition: transform 0.15s ease;
    `;
    fab.onmouseenter = () => fab.style.transform = 'scale(1.05)';
    fab.onmouseleave = () => fab.style.transform = 'scale(1)';

    fab.addEventListener('click', () => open_report_issue_dialog());
    document.body.appendChild(fab);
});

function open_report_issue_dialog() {
    let current_route = window.location.href;
    let current_doctype = cur_frm ? cur_frm.doc.doctype : null;
    let current_docname = cur_frm ? cur_frm.doc.name : null;

    let d = new frappe.ui.Dialog({
        title: 'Report an Issue',
        fields: [
            {
                fieldname: 'subject',
                fieldtype: 'Data',
                label: 'Subject',
                reqd: 1
            },
            {
                fieldname: 'description',
                fieldtype: 'Text Editor',
                label: 'Describe the issue',
                reqd: 1
            },{
                fieldname: 'section_break',
                fieldtype: 'Section Break'  
            },
            {
                fieldname: 'priority',
                fieldtype: 'Select',
                label: 'Priority',
                options: 'Low\nMedium\nHigh\nUrgent',
                default: 'Medium'
            },
            {
                fieldname: 'column_break',
                fieldtype: 'Column Break'
            },
            {
                fieldname: 'issue_type',
                fieldtype: 'Link',
                label: 'Issue Type',
                options: 'Issue Type'
            },
            {
                fieldname: 'section_break',
                fieldtype: 'Section Break'  
            },
            {
                fieldname: 'screenshot',
                fieldtype: 'Attach Image',
                label: 'Screenshot (optional)'
            },
            {
                fieldname: 'context_html',
                fieldtype: 'HTML',
                options: `<div class="text-muted small">
                    Page: ${current_route}<br>
                    ${current_doctype ? `Document: ${current_doctype} - ${current_docname}` : ''}
                </div>`
            }
        ],
        primary_action_label: 'Submit',
        primary_action(values) {
            frappe.call({
                method: 'gicore.gi_support.api.report_issue.create_issue',
                args: {
                    subject: values.subject,
                    description: values.description,
                    priority: values.priority,
                    screenshot: values.screenshot,
                    route: current_route,
                    reference_doctype: current_doctype,
                    reference_name: current_docname
                },
                freeze: true,
                freeze_message: 'Submitting...',
                callback(r) {
                    if (r.message) {
                        d.hide();
                        frappe.show_alert({
                            message: `Issue ${r.message} submitted. Thank you!`,
                            indicator: 'green'
                        }, 5);
                    }
                }
            });
        }
    });
    d.show();
}