
// if (!document.getElementById('freshworks-help-btn')) {
//   var btn = document.createElement('button');
//   btn.id = 'freshworks-help-btn';
//   btn.type = 'button';
//   btn.title = 'Contact Support';
// //   btn.onclick = open_report_issue_dialog();
//   btn.className = 'my-help-btn';
//   btn.textContent = 'Help';

//   document.body.appendChild(btn);

//    btn.onmouseenter = () => btn.style.transform = 'scale(1.05)';
//     btn.onmouseleave = () => btn.style.transform = 'scale(1)';

//     btn.addEventListener('click', () => open_report_issue_dialog());
//     document.body.appendChild(btn);


// //     document.body.appendChild(fab);
// //   window.addEventListener('fw:widget:loaded', function () {
// //     if (typeof FreshworksWidget === 'function') {
// //       FreshworksWidget('hide', 'launcher');
// //     }
// //   });
// }

// function open_report_issue_dialog() {
//     let current_route = window.location.href;
//     let current_doctype = cur_frm ? cur_frm.doc.doctype : null;
//     let current_docname = cur_frm ? cur_frm.doc.name : null;

//     let d = new frappe.ui.Dialog({
//         title: 'Report an Issue',
//         fields: [
//             {
//                 fieldname: 'subject',
//                 fieldtype: 'Data',
//                 label: 'Subject',
//                 reqd: 1
//             },
//             {
//                 fieldname: 'description',
//                 fieldtype: 'Text Editor',
//                 label: 'Describe the issue',
//                 reqd: 1
//             },{
//                 fieldname: 'section_break',
//                 fieldtype: 'Section Break'  
//             },
//             {
//                 fieldname: 'priority',
//                 fieldtype: 'Select',
//                 label: 'Priority',
//                 options: 'Low\nMedium\nHigh\nUrgent',
//                 default: 'Medium'
//             },
//             {
//                 fieldname: 'column_break',
//                 fieldtype: 'Column Break'
//             },
//             {
//                 fieldname: 'issue_type',
//                 fieldtype: 'Link',
//                 label: 'Issue Type',
//                 options: 'Issue Type'
//             },
//             {
//                 fieldname: 'section_break',
//                 fieldtype: 'Section Break'  
//             },
//             {
//                 fieldname: 'screenshot',
//                 fieldtype: 'Attach Image',
//                 label: 'Screenshot (optional)'
//             },
//             {
//                 fieldname: 'context_html',
//                 fieldtype: 'HTML',
//                 options: `<div class="text-muted small">
//                     Page: ${current_route}<br>
//                     ${current_doctype ? `Document: ${current_doctype} - ${current_docname}` : ''}
//                 </div>`
//             }
//         ],
//         primary_action_label: 'Submit',
//         primary_action(values) {
//             frappe.call({
//                 method: 'gicore.gi_support.api.report_issue.create_issue',
//                 args: {
//                     subject: values.subject,
//                     description: values.description,
//                     priority: values.priority,
//                     screenshot: values.screenshot,
//                     route: current_route,
//                     reference_doctype: current_doctype,
//                     reference_name: current_docname
//                 },
//                 // freeze: true,
//                 // freeze_message: 'Submitting...',
//                 callback(r) {
//                     if (r.message) {
//                         d.hide();
//                         frappe.show_alert({
//                             message: `Issue ${r.message} submitted. Thank you!`,
//                             indicator: 'green'
//                         }, 5);
//                     }
//                 }
//             });
//         }
//     });
//     d.show();
// }


if (!document.getElementById('freshworks-help-btn')) {
    var btn = document.createElement('button');
    btn.id = 'freshworks-help-btn';
    btn.type = 'button';
    btn.title = 'Contact Support';
    btn.className = 'my-help-btn';
    btn.textContent = 'Help';

    document.body.appendChild(btn);

    btn.onmouseenter = () => btn.style.transform = 'scale(1.05)';
    btn.onmouseleave = () => btn.style.transform = 'scale(1)';
    btn.addEventListener('click', () => open_report_issue_dialog());
}

// Floating "My Issues" button, stacked above the Help button
if (!document.getElementById('my-issues-fab')) {
    var issuesBtn = document.createElement('button');
    issuesBtn.id = 'my-issues-fab';
    issuesBtn.type = 'button';
    issuesBtn.title = 'View My Issues';
    issuesBtn.className = 'my-help-btn my-issues-btn';
    issuesBtn.innerHTML = 'My Issues';

    document.body.appendChild(issuesBtn);

    issuesBtn.onmouseenter = () => issuesBtn.style.transform = 'scale(1.05)';
    issuesBtn.onmouseleave = () => issuesBtn.style.transform = 'scale(1)';
    issuesBtn.addEventListener('click', () => show_my_issues_dialog());
}

// Inject CSS once
if (!document.getElementById('my-issues-widget-style')) {
    const style = document.createElement('style');
    style.id = 'my-issues-widget-style';
    style.textContent = `
        .my-help-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #D50000;
            color: white;
            border: none;
            padding: 10px 16px;
            border-radius: 24px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.25);
            cursor: pointer;
            z-index: 9999;
            font-size: 13px;
            font-weight: 500;
            transition: transform 0.15s ease;
        }
        .my-issues-btn {
            bottom: 72px;
            background: #010BCE;
        }
        .issue-list {
            display: flex;
            flex-direction: column;
            gap: 10px;
            max-height: 60vh;
            overflow-y: auto;
            padding: 4px 2px;
        }
        .issue-card {
            border: 1px solid #e0e0e0;
            border-radius: 10px;
            padding: 12px 14px;
            cursor: pointer;
            transition: box-shadow 0.15s ease, transform 0.1s ease;
            background: #fff;
        }
        .issue-card:hover {
            box-shadow: 0 3px 10px rgba(0,0,0,0.08);
            transform: translateY(-1px);
        }
        .issue-card-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }
        .issue-name {
            font-weight: 600;
            font-size: 12px;
            color: #8d99a6;
        }
        .issue-status-badge, .issue-priority-badge {
            font-size: 11px;
            font-weight: 600;
            padding: 2px 10px;
            border-radius: 12px;
            display: inline-block;
        }
        .issue-subject {
            font-size: 14px;
            font-weight: 500;
            margin: 4px 0 8px 0;
            color: #1a1a1a;
        }
        .issue-card-bottom {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .issue-date {
            font-size: 11px;
            color: #8d99a6;
        }
    `;
    document.head.appendChild(style);
}

function open_report_issue_dialog() {
    let current_route = window.location.href;
    let current_doctype = cur_frm ? cur_frm.doc.doctype : null;
    let current_docname = cur_frm ? cur_frm.doc.name : null;

    let d = new frappe.ui.Dialog({
        title: 'Report an Issue',
        fields: [
            { fieldname: 'subject', fieldtype: 'Data', label: 'Subject', reqd: 1 },
            { fieldname: 'description', fieldtype: 'Text Editor', label: 'Describe the issue', reqd: 1 },
            { fieldname: 'section_break', fieldtype: 'Section Break' },
            { fieldname: 'priority', fieldtype: 'Select', label: 'Priority', options: 'Low\nMedium\nHigh\nUrgent', default: 'Medium' },
            { fieldname: 'column_break', fieldtype: 'Column Break' },
            { fieldname: 'issue_type', fieldtype: 'Link', label: 'Issue Type', options: 'Issue Type' },
            { fieldname: 'section_break_2', fieldtype: 'Section Break' },
            { fieldname: 'screenshot', fieldtype: 'Attach Image', label: 'Screenshot (optional)' },
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
        },
        secondary_action_label: 'View My Issues',
        secondary_action() {
            d.hide();
            show_my_issues_dialog();
        }
    });
    d.show();
}

// -------------------------------
// My Issues Dialog (pure client-side, no custom Python method)
// -------------------------------
function show_my_issues_dialog() {
    let d = new frappe.ui.Dialog({
        title: 'My Reported Issues',
        size: 'large',
        fields: [
            {
                fieldname: 'issues_html',
                fieldtype: 'HTML',
                options: `<div class="my-issues-container" style="min-height:120px;">
                    <div class="text-muted text-center" style="padding:40px 0;">
                        <i class="fa fa-spinner fa-spin"></i> Loading your issues...
                    </div>
                </div>`
            }
        ],
        primary_action_label: 'Report New Issue',
        primary_action() {
            d.hide();
            open_report_issue_dialog();
        }
    });

    // Destroy the dialog's DOM when closed, so it never lingers
    // and never conflicts with the next time it's opened
    d.$wrapper.on('hidden.bs.modal', () => {
        d.$wrapper.remove();
    });

    d.show();

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Issue',
            filters: [
                ['raised_by', '=', frappe.session.user],
                ['status', '!=', 'Closed']
            ],
            fields: ['name', 'subject', 'status', 'priority', 'creation'],
            order_by: 'creation desc',
            limit_page_length: 50
        },
        callback(r) {
            // Scope the lookup to THIS dialog's wrapper only
            const container = d.$wrapper.find('.my-issues-container').get(0);
            if (!container) return; // dialog was closed before response came back

            const issues = r.message || [];

            if (!issues.length) {
                container.innerHTML = `
                    <div class="text-center text-muted" style="padding:40px 0;">
                        <i class="fa fa-inbox" style="font-size:28px; opacity:0.4;"></i>
                        <p style="margin-top:10px;">You haven't reported any issues yet.</p>
                    </div>`;
                return;
            }

            container.innerHTML = `
                <div class="issue-list">
                    ${issues.map(render_issue_card).join('')}
                </div>
            `;

            container.querySelectorAll('.issue-card').forEach(card => {
                card.addEventListener('click', () => {
                    const name = card.getAttribute('data-name');
                    if (document.activeElement && document.activeElement.blur) {
                        document.activeElement.blur();
                    }
                    // d.hide();
                    window.open(frappe.utils.get_form_link('Issue', name), '_blank');
                });
            });
        },
        error() {
            const container = d.$wrapper.find('.my-issues-container').get(0);
            if (container) {
                container.innerHTML = `<div class="text-danger text-center" style="padding:30px 0;">
                    Failed to load issues. Please try again.
                </div>`;
            }
        }
    });
}

function render_issue_card(issue) {
    const statusColors = {
        'Open': '#2b90d9',
        'Replied': '#f39c12',
        'On Hold': '#8d99a6',
        'Resolved': '#28a745',
        'Closed': '#6c757d'
    };
    const priorityColors = {
        'Low': '#8d99a6',
        'Medium': '#f39c12',
        'High': '#D50000',
        'Urgent': '#b30000'
    };

    const statusColor = statusColors[issue.status] || '#8d99a6';
    const priorityColor = priorityColors[issue.priority] || '#8d99a6';
    const date = frappe.datetime.str_to_user(issue.creation);

    return `
        <div class="issue-card" data-name="${issue.name}">
            <div class="issue-card-top">
                <span class="issue-name">${issue.name}</span>
                <span class="issue-status-badge" style="background:${statusColor}1a; color:${statusColor};">
                    ${frappe.utils.escape_html(issue.status)}
                </span>
            </div>
            <div class="issue-subject">${frappe.utils.escape_html(issue.subject || '')}</div>
            <div class="issue-card-bottom">
                <span class="issue-priority-badge" style="background:${priorityColor}1a; color:${priorityColor};">
                    ${frappe.utils.escape_html(issue.priority || 'Medium')}
                </span>
                <span class="issue-date">${date}</span>
            </div>
        </div>
    `;
}