// =====================================================
// gicore/public/js/report_issue_widget.js
// Speed-dial FAB: Help / My Issues / Quick Access (3-level tree)
// =====================================================

(function () {

    // ---------- Inject CSS once ----------
    if (!document.getElementById('gicore-widget-style')) {
        const style = document.createElement('style');
        style.id = 'gicore-widget-style';
        style.textContent = `
            :root {
                --gc-blue: #010BCE;
                --gc-blue-dark: #0008a3;
                --gc-red: #D50000;
                --gc-ink: #1a1d29;
                --gc-muted: #8a90a2;
                --gc-line: #e8e9f0;
                --gc-surface: #ffffff;
                --gc-bg-soft: #f6f7fb;
            }

            /* ---- Speed dial root ---- */
            .gc-dial {
                position: fixed;
                bottom: 24px;
                right: 24px;
                z-index: 9999;
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 12px;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            }

            .gc-dial-main {
                width: 56px;
                height: 56px;
                border-radius: 50%;
                border: none;
                background: linear-gradient(135deg, var(--gc-blue), var(--gc-blue-dark));
                color: #fff;
                box-shadow: 0 6px 20px rgba(1, 11, 206, 0.35);
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: transform 0.25s cubic-bezier(.34,1.56,.64,1), box-shadow 0.25s ease;
            }
            .gc-dial-main:hover {
                box-shadow: 0 8px 26px rgba(1, 11, 206, 0.45);
            }
            .gc-dial-main svg {
                width: 22px;
                height: 22px;
                transition: transform 0.3s ease;
            }
            .gc-dial.gc-open .gc-dial-main svg {
                transform: rotate(135deg);
            }

            .gc-dial-items {
                display: flex;
                flex-direction: column;
                align-items: flex-end;
                gap: 10px;
                margin-bottom: 4px;
            }

            .gc-dial-item {
                display: flex;
                align-items: center;
                gap: 10px;
                opacity: 0;
                transform: translateY(8px) scale(0.9);
                pointer-events: none;
                transition: opacity 0.2s ease, transform 0.2s cubic-bezier(.34,1.56,.64,1);
            }
            .gc-dial.gc-open .gc-dial-item {
                opacity: 1;
                transform: translateY(0) scale(1);
                pointer-events: auto;
            }
            .gc-dial.gc-open .gc-dial-item:nth-child(1) { transition-delay: 0.06s; }
            .gc-dial.gc-open .gc-dial-item:nth-child(2) { transition-delay: 0.03s; }
            .gc-dial.gc-open .gc-dial-item:nth-child(3) { transition-delay: 0s; }

            .gc-dial-label {
                background: var(--gc-ink);
                color: #fff;
                font-size: 12px;
                font-weight: 500;
                padding: 6px 12px;
                border-radius: 8px;
                white-space: nowrap;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }

            .gc-dial-btn {
                width: 44px;
                height: 44px;
                border-radius: 50%;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #fff;
                box-shadow: 0 4px 14px rgba(0,0,0,0.2);
                transition: transform 0.15s ease;
            }
            .gc-dial-btn:hover { transform: scale(1.08); }
            .gc-dial-btn svg { width: 18px; height: 18px; }

            .gc-btn-help { background: var(--gc-red); }
            .gc-btn-issues { background: var(--gc-blue); }
            .gc-btn-modules { background: #6c2bd9; }

            /* ---- Backdrop tint while dial open ---- */
            .gc-dial-scrim {
                position: fixed;
                inset: 0;
                z-index: 9998;
                display: none;
            }
            .gc-dial.gc-open + .gc-dial-scrim { display: block; }

            /* ---- Shared dialog panels ---- */
            .gc-panel-header {
                display: flex;
                align-items: center;
                gap: 10px;
                margin-bottom: 16px;
            }
            .gc-panel-icon {
                width: 36px;
                height: 36px;
                border-radius: 10px;
                display: flex;
                align-items: center;
                justify-content: center;
                color: #fff;
                flex-shrink: 0;
            }
            .gc-panel-icon svg { width: 18px; height: 18px; }
            .gc-panel-sub {
                font-size: 12.5px;
                color: var(--gc-muted);
                margin-top: 1px;
            }

            .gc-empty-state {
                text-align: center;
                padding: 48px 20px;
                color: var(--gc-muted);
            }
            .gc-empty-state svg {
                width: 40px;
                height: 40px;
                opacity: 0.3;
                margin-bottom: 12px;
            }
            .gc-empty-state p {
                font-size: 13.5px;
                margin: 0;
            }

            .gc-loading-state {
                text-align: center;
                padding: 48px 20px;
                color: var(--gc-muted);
                font-size: 13px;
            }
            .gc-spinner {
                width: 22px;
                height: 22px;
                border: 2.5px solid var(--gc-line);
                border-top-color: var(--gc-blue);
                border-radius: 50%;
                margin: 0 auto 12px;
                animation: gc-spin 0.7s linear infinite;
            }
            @keyframes gc-spin { to { transform: rotate(360deg); } }

            /* ---- Issue list ---- */
            .issue-list {
                display: flex;
                flex-direction: column;
                gap: 8px;
                max-height: 58vh;
                overflow-y: auto;
                padding: 2px 2px 4px;
            }
            .issue-card {
                border: 1px solid var(--gc-line);
                border-radius: 12px;
                padding: 13px 15px;
                cursor: pointer;
                background: var(--gc-surface);
                transition: border-color 0.15s ease, box-shadow 0.15s ease, transform 0.1s ease;
            }
            .issue-card:hover {
                border-color: var(--gc-blue);
                box-shadow: 0 4px 14px rgba(1, 11, 206, 0.08);
                transform: translateY(-1px);
            }
            .issue-card-top {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 6px;
            }
            .issue-name {
                font-weight: 700;
                font-size: 11.5px;
                color: var(--gc-muted);
                letter-spacing: 0.2px;
            }
            .badge {
                font-size: 10.5px;
                font-weight: 700;
                padding: 3px 10px;
                border-radius: 20px;
                display: inline-block;
                letter-spacing: 0.2px;
            }
            .issue-subject {
                font-size: 14px;
                font-weight: 600;
                color: var(--gc-ink);
                margin-bottom: 8px;
                line-height: 1.3;
            }
            .issue-card-bottom {
                display: flex;
                justify-content: space-between;
                align-items: center;
            }
            .issue-date {
                font-size: 11.5px;
                color: var(--gc-muted);
            }
            .badge-open { background: #2b90d91a; color: #2b90d9; }
            .badge-replied { background: #f39c121a; color: #f39c12; }
            .badge-onhold { background: #8d99a61a; color: #8d99a6; }
            .badge-resolved { background: #28a7451a; color: #28a745; }
            .badge-closed { background: #6c757d1a; color: #6c757d; }
            .badge-low { background: #8d99a61a; color: #8d99a6; }
            .badge-medium { background: #f39c121a; color: #f39c12; }
            .badge-high { background: #D500001a; color: #D50000; }
            .badge-urgent { background: #b300001a; color: #b30000; }
            .badge-page { background: #2b90d91a; color: #2b90d9; }
            .badge-report { background: #6c2bd91a; color: #6c2bd9; }

            /* ---- Quick Access 3-level tree ---- */
            .qa-tree {
                display: flex;
                flex-direction: column;
                gap: 6px;
                max-height: 60vh;
                overflow-y: auto;
                padding: 2px 2px 4px;
            }

            /* Level 1: Module */
            .qa-module {
                border: 1px solid var(--gc-line);
                border-radius: 10px;
                overflow: hidden;
                background: var(--gc-surface);
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
            .qa-module-head:hover { background: var(--gc-bg-soft); }
            .qa-module-icon {
                width: 28px;
                height: 28px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: var(--gc-blue);
                color: #fff;
                flex-shrink: 0;
            }
            .qa-module-icon svg { width: 14px; height: 14px; }
            .qa-module-title {
                font-size: 13.5px;
                font-weight: 700;
                color: var(--gc-ink);
                flex: 1;
            }
            .qa-count {
                font-size: 11px;
                font-weight: 600;
                color: var(--gc-muted);
                background: var(--gc-bg-soft);
                padding: 2px 8px;
                border-radius: 10px;
            }

            /* NOTE: accordion open/close is driven purely by the .qa-open class
               toggling max-height between 0 and a generous fixed cap. We
               deliberately do NOT measure scrollHeight in JS anymore — see
               bind_qa_tree_events() for why that was buggy. */
            .qa-module-body {
                max-height: 0;
                overflow: hidden;
                transition: max-height 0.3s ease;
                background: var(--gc-bg-soft);
                padding: 0 10px;
            }
            .qa-module.qa-open > .qa-module-body {
                max-height: 2000px;
            }

            /* Level 2: Pages / Reports category */
            .qa-category {
                border-radius: 8px;
                margin: 8px 0;
                background: var(--gc-surface);
                border: 1px solid var(--gc-line);
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
            .qa-category-head:hover { background: var(--gc-bg-soft); }
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

            /* Chevrons (shared) */
            .qa-chevron {
                width: 15px;
                height: 15px;
                flex-shrink: 0;
                color: var(--gc-muted);
                transition: transform 0.2s ease;
            }
            .qa-module.qa-open > .qa-module-head .qa-chevron { transform: rotate(90deg); }
            .qa-category.qa-open > .qa-category-head .qa-chevron { transform: rotate(90deg); }

            /* Level 3: individual leaf item */
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
                background: var(--gc-bg-soft);
                border: 1px solid transparent;
                transition: border-color 0.15s ease, transform 0.1s ease, background 0.15s ease;
            }
            .qa-leaf:hover {
                border-color: var(--gc-blue);
                background: var(--gc-surface);
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
                color: var(--gc-ink);
                flex: 1;
            }
        `;
        document.head.appendChild(style);
    }

    // ---------- Icons (inline SVG, stroke-based) ----------
    const ICONS = {
        plus: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>`,
        help: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M9.5 9a2.5 2.5 0 0 1 4.7 1.2c0 1.6-2.2 2-2.2 3.3"/><circle cx="12" cy="17" r="0.4" fill="currentColor"/></svg>`,
        list: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01"/></svg>`,
        grid: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>`,
        inbox: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 12h4l2 3h4l2-3h4"/><path d="M5.5 5h13L21 12v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-6L5.5 5z"/></svg>`,
        folder: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7z"/></svg>`,
        file: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/></svg>`,
        chart: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M18 17V9M13 17V5M8 17v-4"/></svg>`,
        chevron: `<svg class="qa-chevron" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 6l6 6-6 6"/></svg>`
    };

    // ---------- Build speed dial ----------
    if (!document.getElementById('gc-dial')) {
        const wrap = document.createElement('div');
        wrap.className = 'gc-dial';
        wrap.id = 'gc-dial';
        wrap.innerHTML = `
            <div class="gc-dial-items">
                <div class="gc-dial-item">
                    <span class="gc-dial-label">Quick access</span>
                    <button class="gc-dial-btn gc-btn-modules" title="Quick Access">${ICONS.grid}</button>
                </div>
                <div class="gc-dial-item">
                    <span class="gc-dial-label">My issues</span>
                    <button class="gc-dial-btn gc-btn-issues" title="My Issues">${ICONS.list}</button>
                </div>
                <div class="gc-dial-item">
                    <span class="gc-dial-label">Report an issue</span>
                    <button class="gc-dial-btn gc-btn-help" title="Report an Issue">${ICONS.help}</button>
                </div>
            </div>
            <button class="gc-dial-main" id="gc-dial-main">${ICONS.plus}</button>
        `;
        document.body.appendChild(wrap);

        const scrim = document.createElement('div');
        scrim.className = 'gc-dial-scrim';
        wrap.after(scrim);

        function closeDial() { wrap.classList.remove('gc-open'); }
        function toggleDial() { wrap.classList.toggle('gc-open'); }

        wrap.querySelector('#gc-dial-main').addEventListener('click', toggleDial);
        scrim.addEventListener('click', closeDial);

        wrap.querySelector('.gc-btn-modules').addEventListener('click', () => { closeDial(); show_quick_modules_dialog(); });
        wrap.querySelector('.gc-btn-issues').addEventListener('click', () => { closeDial(); show_my_issues_dialog(); });
        wrap.querySelector('.gc-btn-help').addEventListener('click', () => { closeDial(); open_report_issue_dialog(); });
    }

    // ---------- Helper: blur before hiding dialog (a11y fix) ----------
      function blurAndHide(d) {
        if (document.activeElement && document.activeElement.blur) {
            document.activeElement.blur();
        }
        d.hide();

        // Force-clean any leftover Bootstrap modal backdrop/state.
        // Needed because navigating away (frappe.set_route) right after
        // d.hide() can interrupt the modal's hide animation, leaving a
        // dark backdrop stuck on top of the page underneath.
        setTimeout(() => {
            document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
            document.body.classList.remove('modal-open');
            document.body.style.removeProperty('overflow');
            document.body.style.removeProperty('padding-right');
        }, 300); // matches Bootstrap's default modal fade duration
    }

    // =====================================================
    // Report an Issue dialog
    // =====================================================
    window.open_report_issue_dialog = function () {
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

        d.$wrapper.on('hidden.bs.modal', () => d.$wrapper.remove());
        d.show();
    };

    // =====================================================
    // My Issues dialog
    // =====================================================
    window.show_my_issues_dialog = function () {
        let d = new frappe.ui.Dialog({
            title: 'My Reported Issues',
            size: 'large',
            fields: [
                {
                    fieldname: 'issues_html',
                    fieldtype: 'HTML',
                    options: `
                        <div class="gc-panel-header">
                            <div class="gc-panel-icon" style="background: var(--gc-blue);">${ICONS.inbox}</div>
                            <div>
                                <div style="font-weight:700; font-size:14px;">Your submitted issues</div>
                                <div class="gc-panel-sub">Click any issue to open its full record</div>
                            </div>
                        </div>
                        <div class="my-issues-container">
                            <div class="gc-loading-state">
                                <div class="gc-spinner"></div>
                                Loading your issues…
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

        d.$wrapper.on('hidden.bs.modal', () => d.$wrapper.remove());
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
                const container = d.$wrapper.find('.my-issues-container').get(0);
                if (!container) return;

                const issues = r.message || [];

                if (!issues.length) {
                    container.innerHTML = `
                        <div class="gc-empty-state">
                            ${ICONS.inbox}
                            <p>You haven't reported any issues yet.</p>
                        </div>`;
                    return;
                }

                container.innerHTML = `<div class="issue-list">${issues.map(render_issue_card).join('')}</div>`;

                container.querySelectorAll('.issue-card').forEach(card => {
                    card.addEventListener('click', () => {
                        const name = card.getAttribute('data-name');
                        blurAndHide(d);
                        window.open(frappe.utils.get_form_link('Issue', name), '_blank');
                    });
                });
            },
            error() {
                const container = d.$wrapper.find('.my-issues-container').get(0);
                if (container) {
                    container.innerHTML = `<div class="gc-empty-state">Failed to load issues. Please try again.</div>`;
                }
            }
        });
    };

    function statusClass(status) {
        return {
            'Open': 'badge-open', 'Replied': 'badge-replied', 'On Hold': 'badge-onhold',
            'Resolved': 'badge-resolved', 'Closed': 'badge-closed'
        }[status] || 'badge-onhold';
    }
    function priorityClass(priority) {
        return {
            'Low': 'badge-low', 'Medium': 'badge-medium', 'High': 'badge-high', 'Urgent': 'badge-urgent'
        }[priority] || 'badge-medium';
    }

    function render_issue_card(issue) {
        const date = frappe.datetime.str_to_user(issue.creation);
        return `
            <div class="issue-card" data-name="${issue.name}">
                <div class="issue-card-top">
                    <span class="issue-name">${issue.name}</span>
                    <span class="badge ${statusClass(issue.status)}">${frappe.utils.escape_html(issue.status)}</span>
                </div>
                <div class="issue-subject">${frappe.utils.escape_html(issue.subject || '')}</div>
                <div class="issue-card-bottom">
                    <span class="badge ${priorityClass(issue.priority)}">${frappe.utils.escape_html(issue.priority || 'Medium')}</span>
                    <span class="issue-date">${date}</span>
                </div>
            </div>`;
    }

    // =====================================================
    // Quick Access dialog — 3-level tree
    // Level 1: Module  ->  Level 2: Pages / Reports  ->  Level 3: items
    // (reads "Quick Menu Item" doctype)
    // =====================================================
    window.show_quick_modules_dialog = function () {
        let d = new frappe.ui.Dialog({
            title: 'Quick Access',
            size: 'large',
            fields: [
                {
                    fieldname: 'modules_html',
                    fieldtype: 'HTML',
                    options: `
                        <div class="gc-panel-header">
                            <div class="gc-panel-icon" style="background:#6c2bd9;">${ICONS.grid}</div>
                            <div>
                                <div style="font-weight:700; font-size:14px;">Jump to a page or report</div>
                                <div class="gc-panel-sub">Module → Pages / Reports → item</div>
                            </div>
                        </div>
                        <div class="quick-modules-container">
                            <div class="gc-loading-state">
                                <div class="gc-spinner"></div>
                                Loading modules…
                            </div>
                        </div>`
                }
            ]
        });

        d.$wrapper.on('hidden.bs.modal', () => d.$wrapper.remove());
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
                if (!container) return;

                const items = r.message || [];

                if (!items.length) {
                    container.innerHTML = `
                        <div class="gc-empty-state">
                            ${ICONS.folder}
                            <p>No modules configured yet.</p>
                        </div>`;
                    return;
                }

                // ---- Build 3-level structure: module -> { Page: [...], Report: [...] } ----
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

                bind_qa_tree_events(container, d);

                // Auto-expand the first module for orientation
                const firstModule = container.querySelector('.qa-module');
                if (firstModule) firstModule.classList.add('qa-open');
            },
            error() {
                const container = d.$wrapper.find('.quick-modules-container').get(0);
                if (container) {
                    container.innerHTML = `<div class="gc-empty-state">Failed to load modules. Please try again.</div>`;
                }
            }
        });
    };

    // ---- Level 1: Module node ----
    function render_qa_module(moduleName, buckets) {
        const totalCount = buckets.Page.length + buckets.Report.length;
        return `
            <div class="qa-module" data-module="${frappe.utils.escape_html(moduleName)}">
                <div class="qa-module-head">
                    ${ICONS.chevron}
                    <div class="qa-module-icon">${ICONS.folder}</div>
                    <span class="qa-module-title">${frappe.utils.escape_html(moduleName)}</span>
                    <span class="qa-count">${totalCount}</span>
                </div>
                <div class="qa-module-body">
                    ${buckets.Page.length ? render_qa_category('Pages', 'qa-cat-pages', ICONS.file, buckets.Page) : ''}
                    ${buckets.Report.length ? render_qa_category('Reports', 'qa-cat-reports', ICONS.chart, buckets.Report) : ''}
                </div>
            </div>`;
    }

    // ---- Level 2: Pages / Reports category node ----
    function render_qa_category(title, catClass, icon, catItems) {
        return `
            <div class="qa-category ${catClass}">
                <div class="qa-category-head">
                    ${ICONS.chevron}
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

    // ---- Level 3: individual leaf item ----
    function render_qa_leaf(item) {
        const isPage = item.item_type === 'Page';
        const target = isPage ? item.reference_doctype : item.reference_report;

        return `
            <div class="qa-leaf" data-type="${item.item_type}" data-target="${frappe.utils.escape_html(target || '')}">
                <span class="qa-leaf-dot"></span>
                <span class="qa-leaf-label">${frappe.utils.escape_html(item.label)}</span>
            </div>`;
    }

    // ---- Event binding for the whole tree ----
    // NOTE: this used to compute pixel heights via scrollHeight on both
    // level 1 (module) and level 2 (category) nodes. That was buggy:
    // when a category was opened, its parent module's max-height was
    // re-measured one animation frame later via requestAnimationFrame,
    // but at that point the category's own max-height transition had
    // only just started — so scrollHeight was captured while the
    // category was still visually collapsed. The module's max-height
    // then got locked too small to contain the newly-expanding
    // category, which looked exactly like "the second level won't
    // uncollapse" even though the category's own class/state was
    // correct.
    //
    // Fix: don't measure anything. Just toggle the `qa-open` class on
    // both levels and let CSS transition max-height to a generous
    // fixed cap (2000px / 1000px, see stylesheet above). The outer
    // .qa-tree already scrolls at 60vh so there's no risk of runaway
    // page height.
    function bind_qa_tree_events(container, d) {
        // Level 1: toggle module
        container.querySelectorAll('.qa-module-head').forEach(head => {
            head.addEventListener('click', () => {
                const node = head.closest('.qa-module');
                const isOpen = node.classList.contains('qa-open');

                if (isOpen) {
                    node.classList.remove('qa-open');
                    // also collapse any open categories inside so re-opening
                    // the module later starts from a clean state
                    node.querySelectorAll('.qa-category.qa-open').forEach(cat => {
                        cat.classList.remove('qa-open');
                    });
                } else {
                    node.classList.add('qa-open');
                }
            });
        });

        // Level 2: toggle category (Pages / Reports), stop it from bubbling to module
        container.querySelectorAll('.qa-category-head').forEach(head => {
            head.addEventListener('click', (e) => {
                e.stopPropagation();
                const cat = head.closest('.qa-category');
                cat.classList.toggle('qa-open');
            });
        });

        // Level 3: leaf click -> navigate
        container.querySelectorAll('.qa-leaf').forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                const type = el.getAttribute('data-type');
                const target = el.getAttribute('data-target');
                blurAndHide(d);

                if (type === 'Page') {
                    frappe.set_route('List', target);
                } else if (type === 'Report') {
                    frappe.set_route('query-report', target);
                }
            });
        });
    }

})();