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

// Floating "Quick Access" button, stacked above the My Issues button
if (!document.getElementById('quick-access-fab')) {
    var quickBtn = document.createElement('button');
    quickBtn.id = 'quick-access-fab';
    quickBtn.type = 'button';
    quickBtn.title = 'Quick Access';
    quickBtn.className = 'my-help-btn my-quick-access-btn';
    quickBtn.innerHTML = 'Quick Access';

    document.body.appendChild(quickBtn);

    quickBtn.onmouseenter = () => quickBtn.style.transform = 'scale(1.05)';
    quickBtn.onmouseleave = () => quickBtn.style.transform = 'scale(1)';
    quickBtn.addEventListener('click', () => show_quick_modules_dialog());
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
        .my-quick-access-btn {
            bottom: 124px;
            background: #6c2bd9;
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

        /* ---- Quick Access 3-level tree ---- */
        .qa-tree {
            display: flex;
            flex-direction: column;
            gap: 6px;
            max-height: 60vh;
            overflow-y: auto;
            padding: 2px 2px 4px;
        }
        .qa-module {
            border: 1px solid #e8e9f0;
            border-radius: 10px;
            overflow: hidden;
            background: #fff;
        }
        .qa-module-head {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 12px 14px;
            cursor: pointer;
            user-select: none;
            transition: background 0.15s ease;
        }
        .qa-module-head:hover { background: #f6f7fb; }
        .qa-module-icon {
            width: 28px;
            height: 28px;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            background: #010BCE;
            color: #fff;
            flex-shrink: 0;
        }
        .qa-module-icon svg { width: 14px; height: 14px; }
        .qa-module-title {
            font-size: 13.5px;
            font-weight: 700;
            color: #1a1d29;
            flex: 1;
        }
        .qa-count {
            font-size: 11px;
            font-weight: 600;
            color: #8a90a2;
            background: #f6f7fb;
            padding: 2px 8px;
            border-radius: 10px;
        }

        /* Accordion open/close is driven purely by the .qa-open class
           toggling max-height between 0 and a generous fixed cap.
           No JS scrollHeight measurement — see note in JS below. */
        .qa-module-body {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
            background: #f6f7fb;
            padding: 0 10px;
        }
        .qa-module.qa-open > .qa-module-body {
            max-height: 2000px;
        }

        .qa-category {
            border-radius: 8px;
            margin: 8px 0;
            background: #fff;
            border: 1px solid #e8e9f0;
            overflow: hidden;
        }
        .qa-category-head {
            display: flex;
            align-items: center;
            gap: 9px;
            padding: 9px 12px;
            cursor: pointer;
            user-select: none;
            transition: background 0.15s ease;
        }
        .qa-category-head:hover { background: #f6f7fb; }
        .qa-category-icon {
            width: 22px;
            height: 22px;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            flex-shrink: 0;
        }
        .qa-category-icon svg { width: 11px; height: 11px; }
        .qa-category-title {
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            flex: 1;
        }
        .qa-cat-pages .qa-category-icon { background: #2b90d91a; color: #2b90d9; }
        .qa-cat-pages .qa-category-title { color: #2b90d9; }
        .qa-cat-reports .qa-category-icon { background: #6c2bd91a; color: #6c2bd9; }
        .qa-cat-reports .qa-category-title { color: #6c2bd9; }

        .qa-category-body {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.3s ease;
        }
        .qa-category.qa-open > .qa-category-body {
            max-height: 1000px;
        }

        .qa-chevron {
            width: 15px;
            height: 15px;
            flex-shrink: 0;
            color: #8a90a2;
            transition: transform 0.2s ease;
        }
        .qa-module.qa-open > .qa-module-head .qa-chevron { transform: rotate(90deg); }
        .qa-category.qa-open > .qa-category-head .qa-chevron { transform: rotate(90deg); }

        .qa-leaf-list {
            display: flex;
            flex-direction: column;
            padding: 4px 10px 10px;
            gap: 4px;
        }
        .qa-leaf {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 11px;
            border-radius: 7px;
            cursor: pointer;
            background: #f6f7fb;
            border: 1px solid transparent;
            transition: border-color 0.15s ease, transform 0.1s ease, background 0.15s ease;
        }
        .qa-leaf:hover {
            border-color: #010BCE;
            background: #fff;
            transform: translateX(3px);
        }
        .qa-leaf-dot {
            width: 6px;
            height: 6px;
            border-radius: 50%;
            flex-shrink: 0;
        }
        .qa-cat-pages .qa-leaf-dot { background: #2b90d9; }
        .qa-cat-reports .qa-leaf-dot { background: #6c2bd9; }
        .qa-leaf-label {
            font-size: 13px;
            font-weight: 500;
            color: #1a1d29;
            flex: 1;
        }
        .qa-empty {
            text-align: center;
            padding: 40px 0;
            color: #8a90a2;
        }
    `;
    document.head.appendChild(style);
}

const QA_ICONS = {
    grid: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"></rect><rect x="14" y="3" width="7" height="7" rx="1.5"></rect><rect x="3" y="14" width="7" height="7" rx="1.5"></rect><rect x="14" y="14" width="7" height="7" rx="1.5"></rect></svg>`,
    folder: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"></path></svg>`,
    file: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><path d="M14 2v6h6"></path></svg>`,
    chart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"></path><path d="M18 17V9M13 17V5M8 17v-4"></path></svg>`,
    chevron: `<svg class="qa-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"></path></svg>`
};

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

// -------------------------------
// Quick Access Dialog — 3-level tree
// Level 1: Module -> Level 2: Pages / Reports -> Level 3: items
// (reads "Quick Menu Item" doctype)
// -------------------------------
function show_quick_modules_dialog() {
    let d = new frappe.ui.Dialog({
        title: 'Quick Access',
        size: 'large',
        fields: [
            {
                fieldname: 'modules_html',
                fieldtype: 'HTML',
                options: `<div class="quick-modules-container" style="min-height:120px;">
                    <div class="text-muted text-center" style="padding:40px 0;">
                        <i class="fa fa-spinner fa-spin"></i> Loading modules...
                    </div>
                </div>`
            }
        ]
    });

    d.$wrapper.on('hidden.bs.modal', () => {
        d.$wrapper.remove();
    });

    d.show();

    frappe.call({
        method: 'frappe.client.get_list',
        args: {
            doctype: 'Quick Menu Item',
            fields: ['name', 'module', 'label', 'item_type', 'reference_doctype', 'reference_report'],
            order_by: 'module asc, idx asc',
            limit_page_length: 0
        },
        callback(r) {
            const container = d.$wrapper.find('.quick-modules-container').get(0);
            if (!container) return; // dialog was closed before response came back

            const items = r.message || [];

            if (!items.length) {
                container.innerHTML = `
                    <div class="qa-empty">
                        <i class="fa fa-folder-open" style="font-size:28px; opacity:0.4;"></i>
                        <p style="margin-top:10px;">No modules configured yet.</p>
                    </div>`;
                return;
            }

            // Build 3-level structure: module -> { Page: [...], Report: [...] }
            const tree = {};
            items.forEach(item => {
                if (!tree[item.module]) tree[item.module] = { Page: [], Report: [] };
                const bucket = item.item_type === 'Report' ? 'Report' : 'Page';
                tree[item.module][bucket].push(item);
            });

            const moduleNames = Object.keys(tree);

            container.innerHTML = `
                <div class="qa-tree">
                    ${moduleNames.map(name => render_qa_module(name, tree[name])).join('')}
                </div>`;

            bind_qa_tree_events(container);

            // Auto-expand the first module for orientation
            const firstModule = container.querySelector('.qa-module');
            if (firstModule) firstModule.classList.add('qa-open');
        },
        error() {
            const container = d.$wrapper.find('.quick-modules-container').get(0);
            if (container) {
                container.innerHTML = `<div class="text-danger text-center" style="padding:30px 0;">
                    Failed to load modules. Please try again.
                </div>`;
            }
        }
    });
}

function render_qa_module(moduleName, buckets) {
    const totalCount = buckets.Page.length + buckets.Report.length;
    return `
        <div class="qa-module" data-module="${frappe.utils.escape_html(moduleName)}">
            <div class="qa-module-head">
                ${QA_ICONS.chevron}
                <div class="qa-module-icon">${QA_ICONS.folder}</div>
                <span class="qa-module-title">${frappe.utils.escape_html(moduleName)}</span>
                <span class="qa-count">${totalCount}</span>
            </div>
            <div class="qa-module-body">
                ${buckets.Page.length ? render_qa_category('Pages', 'qa-cat-pages', QA_ICONS.file, buckets.Page) : ''}
                ${buckets.Report.length ? render_qa_category('Reports', 'qa-cat-reports', QA_ICONS.chart, buckets.Report) : ''}
            </div>
        </div>`;
}

function render_qa_category(title, catClass, icon, catItems) {
    return `
        <div class="qa-category ${catClass}">
            <div class="qa-category-head">
                ${QA_ICONS.chevron}
                <div class="qa-category-icon">${icon}</div>
                <span class="qa-category-title">${title}</span>
                <span class="qa-count">${catItems.length}</span>
            </div>
            <div class="qa-category-body">
                <div class="qa-leaf-list">
                    ${catItems.map(render_qa_leaf).join('')}
                </div>
            </div>
        </div>`;
}

function render_qa_leaf(item) {
    const isPage = item.item_type === 'Page';
    const target = isPage ? item.reference_doctype : item.reference_report;

    return `
        <div class="qa-leaf" data-type="${item.item_type}" data-target="${frappe.utils.escape_html(target || '')}">
            <span class="qa-leaf-dot"></span>
            <span class="qa-leaf-label">${frappe.utils.escape_html(item.label)}</span>
        </div>`;
}

// Accordion state is driven purely by the .qa-open class toggling
// max-height between 0 and a generous fixed cap in CSS. No JS
// scrollHeight measurement — that approach previously caused the
// parent module's max-height to get locked in before its child
// category had actually expanded, clipping the second level.
function bind_qa_tree_events(container) {
    // Level 1: toggle module
    container.querySelectorAll('.qa-module-head').forEach(head => {
        head.addEventListener('click', () => {
            const node = head.closest('.qa-module');
            const isOpen = node.classList.contains('qa-open');

            if (isOpen) {
                node.classList.remove('qa-open');
                node.querySelectorAll('.qa-category.qa-open').forEach(cat => {
                    cat.classList.remove('qa-open');
                });
            } else {
                node.classList.add('qa-open');
            }
        });
    });

    // Level 2: toggle category (Pages / Reports)
    container.querySelectorAll('.qa-category-head').forEach(head => {
        head.addEventListener('click', (e) => {
            e.stopPropagation();
            const cat = head.closest('.qa-category');
            cat.classList.toggle('qa-open');
        });
    });

    // Level 3: leaf click -> open in a new tab, dialog stays open
    container.querySelectorAll('.qa-leaf').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const type = el.getAttribute('data-type');
            const target = el.getAttribute('data-target');
            if (!target) return;

            const url = type === 'Report'
                ? `/app/query-report/${encodeURIComponent(target)}`
                : `/app/${frappe.router.slug(target)}`;

            window.open(url, '_blank');
        });
    });
}