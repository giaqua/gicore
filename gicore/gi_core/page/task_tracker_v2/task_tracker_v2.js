/**
 * task_tracker.js - With Type and Priority Cards
 */

frappe.pages["task-tracker-v2"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title: "Task Tracker",
        single_column: true,
    });

    // Inject page CSS once
    if (!document.getElementById("tt-styles")) {
        const style = document.createElement("style");
        style.id = "tt-styles";
        style.textContent = TT_CSS;
        document.head.appendChild(style);
    }

    // Render skeleton
    $(page.body).html(TT_HTML);

    const state = {
        search: "",
        project: "",
        task_type: "",
        status: "",
        priority: "",
        page: 1,
        page_size: 15,
        tasks: [],
        total: 0,
        loading: false,
        view_mode: "grid",
        current_task: null,
    };

    // ── Populate filter dropdowns ──────────────────────────────────────────
    frappe.call({
        method: "gicore.gi_core.page.task_tracker_v2.task_tracker_v2.get_filter_options",
        callback: function (r) {
            const { projects, task_types } = r.message;

            const $proj = $("#tt-filter-project");
            projects.forEach(p => {
                $proj.append(`<option value="${p.name}">${p.project_name || p.name}</option>`);
            });

            const $type = $("#tt-filter-type");
            task_types.forEach(t => {
                $type.append(`<option value="${t}">${t}</option>`);
            });
        },
    });

    // ── Add Task button in page header ─────────────────────────────────────
    page.set_primary_action(__("New Task"), () => open_add_dialog(state, load), "octicon octicon-plus");
    
    // Add view toggle
    page.add_menu_item(__("Grid View"), () => {
        state.view_mode = "grid";
        render_tasks(state.tasks, state);
    });
    page.add_menu_item(__("Compact View"), () => {
        state.view_mode = "compact";
        render_tasks(state.tasks, state);
    });

    // ── Filter events ──────────────────────────────────────────────────────
    let search_timer;
    $("#tt-search").on("input", function () {
        clearTimeout(search_timer);
        search_timer = setTimeout(() => {
            state.search = this.value.trim();
            state.page = 1;
            load();
        }, 320);
    });

    ["#tt-filter-project", "#tt-filter-type", "#tt-filter-status", "#tt-filter-priority"].forEach(sel => {
        $(sel).on("change", function () {
            if (sel === "#tt-filter-project") state.project = this.value;
            if (sel === "#tt-filter-type") state.task_type = this.value;
            if (sel === "#tt-filter-status") state.status = this.value;
            if (sel === "#tt-filter-priority") state.priority = this.value;
            state.page = 1;
            load();
        });
    });

    $("#tt-clear-filters").on("click", () => {
        state.search = state.project = state.task_type = state.status = state.priority = "";
        state.page = 1;
        $("#tt-search").val("");
        $("#tt-filter-project, #tt-filter-type, #tt-filter-status, #tt-filter-priority").val("");
        load();
    });

    // ── Close review panel ─────────────────────────────────────────────────
    $(document).on("click", "#tt-panel-close, #tt-overlay", () => close_panel());

    // ── Initial load ───────────────────────────────────────────────────────
    load();

    // ══════════════════════════════════════════════════════════════════════
    // Helper Functions
    // ══════════════════════════════════════════════════════════════════════
    function openTaskInNewTab(task_name) {
        window.open(`/app/task/${task_name}`, '_blank');
    }

    function updateSidebarTask(task_name, field, value) {
        if (state.current_task === task_name) {
            const $panel = $("#tt-review-panel");
            
            if (field === "status") {
                const stat_cls = `tt-status-${value.toLowerCase().replace(/ /g, "-")}`;
                const $statusBadge = $panel.find(".tt-panel-meta .tt-badge");
                $statusBadge.removeClass().addClass(`tt-badge ${stat_cls}`).text(value);
                $panel.find(".tt-panel-status-select").val(value);
            }
            
            if (field === "progress") {
                const pct = parseInt(value || 0);
                $panel.find(".tt-progress-fill").css("width", `${pct}%`).css("background", progress_color(pct));
                $panel.find(".tt-detail-row:contains('Progress') span").text(`${pct}%`);
            }
            
            frappe.show_alert({ message: `${field} updated to <b>${value}</b>`, indicator: "green" }, 2);
        }
    }

    // ══════════════════════════════════════════════════════════════════════
    // Core load function
    // ══════════════════════════════════════════════════════════════════════
    function load() {
        if (state.loading) return;
        state.loading = true;
        set_loading(true);

        frappe.call({
            method: "gicore.gi_core.page.task_tracker_v2.task_tracker_v2.get_tasks",
            args: {
                search: state.search,
                project: state.project,
                task_type: state.task_type,
                status: state.status,
                priority: state.priority,
                page: state.page,
                page_size: state.page_size,
            },
            callback: function (r) {
                state.loading = false;
                set_loading(false);
                const { tasks, total, status_counts, type_counts, priority_counts } = r.message;
                state.tasks = tasks;
                state.total = total;

                render_stat_bars(status_counts, type_counts, priority_counts);
                render_tasks(tasks, state);
                render_pagination(total, state);
            },
            error: function () {
                state.loading = false;
                set_loading(false);
                $("#tt-task-list").html(
                    `<div class="tt-empty">
                        <i class="fa fa-exclamation-circle"></i>
                        <p>Failed to load tasks. Check the browser console.</p>
                    </div>`
                );
            },
        });
    }

    // ══════════════════════════════════════════════════════════════════════
    // Render Statistics Bars (Status, Type, Priority)
    // ══════════════════════════════════════════════════════════════════════
    function render_stat_bars(status_counts, type_counts, priority_counts) {
        // Status Cards
        const statusItems = [
            { label: "All", value: status_counts.total, cls: "tt-stat-total", icon: "fa-tasks", filter: "", filterType: "status" },
            { label: "Open", value: status_counts.open, cls: "tt-stat-open", icon: "fa-play-circle", filter: "Open", filterType: "status" },
            { label: "Working", value: status_counts.working, cls: "tt-stat-working", icon: "fa-cog", filter: "Working", filterType: "status" },
            { label: "Overdue", value: status_counts.overdue, cls: "tt-stat-overdue", icon: "fa-exclamation-triangle", filter: "Overdue", filterType: "status" },
            { label: "Completed", value: status_counts.completed, cls: "tt-stat-completed", icon: "fa-check-circle", filter: "Completed", filterType: "status" },
        ];
        
        // Type Cards
        const typeItems = Object.keys(type_counts).map(type => ({
            label: type,
            value: type_counts[type],
            cls: "tt-stat-type",
            icon: "fa-tag",
            filter: type,
            filterType: "type"
        }));
        
        // Priority Cards
        const priorityItems = [
            { label: "Low", value: priority_counts.low, cls: "tt-pri-low-card", icon: "fa-arrow-down", filter: "Low", filterType: "priority" },
            { label: "Medium", value: priority_counts.medium, cls: "tt-pri-medium-card", icon: "fa-minus", filter: "Medium", filterType: "priority" },
            { label: "High", value: priority_counts.high, cls: "tt-pri-high-card", icon: "fa-arrow-up", filter: "High", filterType: "priority" },
            { label: "Urgent", value: priority_counts.urgent, cls: "tt-pri-urgent-card", icon: "fa-exclamation", filter: "Urgent", filterType: "priority" },
        ];
        
        // Render Status Section
        $("#tt-stats-status").html(
            statusItems.map(i => `
                <div class="tt-stat ${i.cls} ${state.status === i.filter ? 'tt-stat-active' : ''}" 
                     data-filter="${i.filter}" data-filter-type="status">
                    <i class="fa ${i.icon} tt-stat-icon"></i>
                    <div>
                        <div class="tt-stat-val">${i.value}</div>
                        <div class="tt-stat-lbl">${i.label}</div>
                    </div>
                </div>
            `).join("")
        );
        
        // Render Type Section (only if there are types)
        if (typeItems.length > 0) {
            $("#tt-stats-type-section").show();
            $("#tt-stats-type").html(
                typeItems.map(i => `
                    <div class="tt-stat ${i.cls} ${state.task_type === i.filter ? 'tt-stat-active' : ''}" 
                         data-filter="${i.filter}" data-filter-type="type">
                        <i class="fa ${i.icon} tt-stat-icon"></i>
                        <div>
                            <div class="tt-stat-val">${i.value}</div>
                            <div class="tt-stat-lbl">${i.label}</div>
                        </div>
                    </div>
                `).join("")
            );
        } else {
            $("#tt-stats-type-section").hide();
        }
        
        // Render Priority Section
        $("#tt-stats-priority").html(
            priorityItems.map(i => `
                <div class="tt-stat ${i.cls} ${state.priority === i.filter ? 'tt-stat-active' : ''}" 
                     data-filter="${i.filter}" data-filter-type="priority">
                    <i class="fa ${i.icon} tt-stat-icon"></i>
                    <div>
                        <div class="tt-stat-val">${i.value}</div>
                        <div class="tt-stat-lbl">${i.label}</div>
                    </div>
                </div>
            `).join("")
        );
        
        // Attach click handlers for all stat cards
        $(".tt-stat").off("click").on("click", function() {
            const filter = $(this).data("filter");
            const filterType = $(this).data("filter-type");
            
            if (filterType === "status") {
                if (filter) {
                    state.status = filter;
                    $("#tt-filter-status").val(filter);
                } else {
                    state.status = "";
                    $("#tt-filter-status").val("");
                }
            } else if (filterType === "type") {
                if (filter) {
                    state.task_type = filter;
                    $("#tt-filter-type").val(filter);
                } else {
                    state.task_type = "";
                    $("#tt-filter-type").val("");
                }
            } else if (filterType === "priority") {
                if (filter) {
                    state.priority = filter;
                    $("#tt-filter-priority").val(filter);
                } else {
                    state.priority = "";
                    $("#tt-filter-priority").val("");
                }
            }
            
            state.page = 1;
            load();
        });
    }

    function render_tasks(tasks, state) {
        const $list = $("#tt-task-list");
        const isGrid = state.view_mode === "grid";

        if (!tasks.length) {
            $list.html(
                `<div class="tt-empty">
                    <i class="fa fa-inbox"></i>
                    <p>No tasks match your filters.</p>
                    <button class="tt-btn-link" id="tt-clear-filters-empty">Clear filters</button>
                </div>`
            );
            $("#tt-clear-filters-empty").off("click").on("click", () => $("#tt-clear-filters").trigger("click"));
            return;
        }

        $list.removeClass("tt-list-view tt-grid-view").addClass(isGrid ? "tt-grid-view" : "tt-list-view");

        const rows = tasks.map(t => {
            const due_str = t.exp_end_date ? frappe.datetime.str_to_user(t.exp_end_date) : "—";
            const overdue = t.exp_end_date &&
                frappe.datetime.get_diff(frappe.datetime.nowdate(), t.exp_end_date) > 0 &&
                t.status !== "Completed" &&
                t.status !== "Cancelled";
            const pct = parseInt(t.progress || 0);
            const pri_cls = `tt-pri-${(t.priority || "medium").toLowerCase()}`;
            const stat_cls = `tt-status-${(t.status || "open").toLowerCase().replace(/ /g, "-")}`;

            if (isGrid) {
                return `
                <div class="tt-card-grid" data-task="${t.name}">
                    <div class="tt-grid-header">
                        <span class="tt-priority-badge ${pri_cls}">${t.priority || "Med"}</span>
                        <span class="tt-badge-sm ${stat_cls}">${(t.status || "Open").substring(0, 3)}</span>
                    </div>
                    <div class="tt-grid-title" title="${escape_html(t.subject || t.name)}">
                        ${escape_html((t.subject || t.name).substring(0, 60))}${(t.subject || t.name).length > 60 ? '...' : ''}
                    </div>
                    <div class="tt-grid-meta">
                        ${t.project ? `<span><i class="fa fa-folder-o"></i> ${escape_html(t.project)}</span>` : ""}
                        ${t.type ? `<span><i class="fa fa-tag"></i> ${escape_html(t.type)}</span>` : ""}
                        <span class="${overdue ? "tt-overdue-date" : ""}"><i class="fa fa-calendar-o"></i> ${due_str}</span>
                    </div>
                    <div class="tt-progress-compact">
                        <div class="tt-progress-bar">
                            <div class="tt-progress-fill" style="width:${pct}%;background:${progress_color(pct)};"></div>
                        </div>
                        <span class="tt-progress-pct">${pct}%</span>
                    </div>
                    <div class="tt-grid-actions">
                        <select class="tt-status-select" data-task="${t.name}" onclick="event.stopPropagation()">
                            ${status_options(t.status)}
                        </select>
                        <button class="tt-icon-btn" data-task="${t.name}" onclick="event.stopPropagation()" title="Open in new tab">
                            <i class="fa fa-external-link"></i>
                        </button>
                    </div>
                </div>`;
            } else {
                return `
                <div class="tt-card-compact" data-task="${t.name}">
                    <div class="tt-compact-priority">
                        <span class="tt-priority-dot ${pri_cls}"></span>
                    </div>
                    <div class="tt-compact-info">
                        <div class="tt-compact-title">${escape_html(t.subject || t.name)}</div>
                        <div class="tt-compact-meta">
                            ${t.project ? `<span><i class="fa fa-folder-o"></i> ${escape_html(t.project)}</span>` : ""}
                            ${t.type ? `<span><i class="fa fa-tag"></i> ${escape_html(t.type)}</span>` : ""}
                            <span class="${overdue ? "tt-overdue-date" : ""}"><i class="fa fa-calendar-o"></i> ${due_str}</span>
                        </div>
                        <div class="tt-progress-tiny">
                            <div class="tt-progress-bar">
                                <div class="tt-progress-fill" style="width:${pct}%;background:${progress_color(pct)};"></div>
                            </div>
                        </div>
                    </div>
                    <div class="tt-compact-status">
                        <span class="tt-badge-sm ${stat_cls}">${t.status || "Open"}</span>
                        <select class="tt-status-select-sm" data-task="${t.name}" onclick="event.stopPropagation()">
                            ${status_options(t.status)}
                        </select>
                        <button class="tt-icon-btn-sm" data-task="${t.name}" onclick="event.stopPropagation()" title="Open in new tab">
                            <i class="fa fa-external-link"></i>
                        </button>
                    </div>
                </div>`;
            }
        }).join("");

        $list.html(rows);

        $list.find("[data-task]").off("click").on("click", function(e) {
            if ($(e.target).closest("select, button").length) return;
            open_review_panel($(this).data("task"));
        });

        $list.find(".tt-status-select, .tt-status-select-sm").off("change").on("change", function() {
            const $sel = $(this);
            const task_name = $sel.data("task");
            const new_status = $sel.val();

            frappe.call({
                method: "gicore.gi_core.page.task_tracker_v2.task_tracker_v2.update_task_status",
                args: { task_name, status: new_status },
                callback: function() {
                    frappe.show_alert({ message: `Status → ${new_status}`, indicator: "green" }, 2);
                    updateSidebarTask(task_name, "status", new_status);
                    load();
                },
            });
        });

        $list.find(".tt-icon-btn, .tt-icon-btn-sm").off("click").on("click", function(e) {
            e.stopPropagation();
            openTaskInNewTab($(this).data("task"));
        });
    }

    function render_pagination(total, state) {
        const pages = Math.ceil(total / state.page_size);
        const $pag = $("#tt-pagination");
        if (pages <= 1) {
            $pag.html("");
            return;
        }

        let html = `<div class="tt-pagination-wrapper">`;
        html += `<span class="tt-pag-info">${((state.page-1)*state.page_size)+1} - ${Math.min(state.page*state.page_size, total)} of ${total}</span>`;
        html += `<div class="tt-pag-controls">`;
        if (state.page > 1)
            html += `<button class="tt-pag-btn" id="tt-prev">← Prev</button>`;
        if (state.page < pages)
            html += `<button class="tt-pag-btn" id="tt-next">Next →</button>`;
        html += `</div></div>`;

        $pag.html(html);
        $("#tt-prev").off("click").on("click", () => { state.page--; load(); });
        $("#tt-next").off("click").on("click", () => { state.page++; load(); });
    }

    // ══════════════════════════════════════════════════════════════════════
    // Quick-review slide panel (keep your existing implementation)
    // ══════════════════════════════════════════════════════════════════════
    function open_review_panel(task_name) {
        state.current_task = task_name;
        const $panel = $("#tt-review-panel");
        $panel.find("#tt-panel-body").html(
            `<div class="tt-panel-loading"><i class="fa fa-spinner fa-spin"></i> Loading…</div>`
        );
        $panel.addClass("tt-panel-open");
        $("#tt-overlay").addClass("tt-overlay-active");

        frappe.call({
            method: "gicore.gi_core.page.task_tracker_v2.task_tracker_v2.get_task_detail",
            args: { task_name },
            callback: function(r) {
                const t = r.message;
                const pct = parseInt(t.progress || 0);

                const comments_html = t.comments.length ?
                    t.comments.map(c =>
                        `<div class="tt-comment">
                            <div class="tt-comment-meta">
                                <b>${escape_html(c.comment_by)}</b>
                                <span>${frappe.datetime.str_to_user(c.creation)}</span>
                            </div>
                            <div class="tt-comment-body">${c.content}</div>
                        </div>`
                    ).join("") :
                    `<p class="tt-muted">No comments yet.</p>`;

                $panel.find("#tt-panel-body").html(`
                    <div class="tt-panel-header">
                        <h3>${escape_html(t.subject)}</h3>
                        <div class="tt-panel-meta">
                            <span class="tt-badge tt-status-${(t.status || "open").toLowerCase().replace(/ /g, "-")}">${t.status}</span>
                            <span class="tt-priority-badge tt-pri-${(t.priority || "medium").toLowerCase()}">${t.priority || "Medium"}</span>
                        </div>
                    </div>
                    <div class="tt-panel-details">
                        <div class="tt-detail-row"><label>Project:</label><span>${escape_html(t.project || "—")}</span></div>
                        <div class="tt-detail-row"><label>Task Type:</label><span>${escape_html(t.type || "—")}</span></div>
                        <div class="tt-detail-row"><label>Due Date:</label><span>${t.exp_end_date || "—"}</span></div>
                        <div class="tt-detail-row"><label>Progress:</label><span>${pct}%</span></div>
                    </div>
                    <div class="tt-progress-bar tt-progress-bar-lg">
                        <div class="tt-progress-fill" style="width:${pct}%;background:${progress_color(pct)};"></div>
                    </div>
                    <div class="tt-panel-field">
                        <label>Update Status:</label>
                        <select class="tt-panel-status-select" data-task="${t.name}" style="width: 100%; padding: 6px; margin-top: 4px;">
                            ${status_options(t.status)}
                        </select>
                    </div>
                    ${t.description ? `<div class="tt-panel-desc"><label>Description:</label><div>${t.description}</div></div>` : ""}
                    <div class="tt-panel-comments">
                        <label>Comments (${t.comments.length})</label>
                        <div class="tt-comments-list">${comments_html}</div>
                        <div class="tt-add-comment" style="margin-top: 12px;">
                            <textarea class="tt-new-comment" placeholder="Add a comment..." rows="2" style="width: 100%; padding: 8px; border: 1px solid var(--border-color); border-radius: 4px;"></textarea>
                            <button class="tt-btn-primary tt-add-comment-btn" data-task="${t.name}" style="margin-top: 8px; width: auto; padding: 6px 12px;">Add Comment</button>
                        </div>
                    </div>
                    <div class="tt-panel-actions">
                        <button class="tt-btn-primary tt-btn-open-full" data-task="${t.name}">Open Full Task →</button>
                    </div>
                `);
                
                $panel.find(".tt-panel-status-select").off("change").on("change", function() {
                    const $sel = $(this);
                    const task_name = $sel.data("task");
                    const new_status = $sel.val();
                    
                    frappe.call({
                        method: "gicore.gi_core.page.task_tracker_v2.task_tracker_v2.update_task_status",
                        args: { task_name, status: new_status },
                        callback: function() {
                            frappe.show_alert({ message: `Status updated to ${new_status}`, indicator: "green" }, 2);
                            const stat_cls = `tt-status-${new_status.toLowerCase().replace(/ /g, "-")}`;
                            $panel.find(".tt-panel-meta .tt-badge").removeClass().addClass(`tt-badge ${stat_cls}`).text(new_status);
                            load();
                        },
                    });
                });
                
                $panel.find(".tt-add-comment-btn").off("click").on("click", function() {
                    const $btn = $(this);
                    const task_name = $btn.data("task");
                    const $textarea = $panel.find(".tt-new-comment");
                    const comment = $textarea.val().trim();
                    
                    if (!comment) {
                        frappe.msgprint("Please enter a comment.");
                        return;
                    }
                    
                    frappe.call({
                        method: "gicore.gi_core.page.task_tracker_v2.task_tracker_v2.add_comment",
                        args: { task_name, comment: comment },
                        callback: function() {
                            frappe.show_alert({ message: "Comment added", indicator: "green" }, 2);
                            $textarea.val("");
                            open_review_panel(task_name);
                        },
                    });
                });
                
                $panel.find(".tt-btn-open-full").off("click").on("click", function() {
                    openTaskInNewTab($(this).data("task"));
                });
            },
        });
    }

    function close_panel() {
        $("#tt-review-panel").removeClass("tt-panel-open");
        $("#tt-overlay").removeClass("tt-overlay-active");
        state.current_task = null;
    }

    // ══════════════════════════════════════════════════════════════════════
    // Add Task dialog
    // ══════════════════════════════════════════════════════════════════════
    function open_add_dialog(state, reload) {
        const d = new frappe.ui.Dialog({
            title: "New Task",
            fields: [
                { label: "Subject", fieldname: "subject", fieldtype: "Data", reqd: 1 },
                { label: "Project", fieldname: "project", fieldtype: "Link", options: "Project", default: state.project || "" },
                { fieldtype: "Column Break" },
                { label: "Task Type", fieldname: "task_type", fieldtype: "Data", default: state.task_type || "" },
                { label: "Priority", fieldname: "priority", fieldtype: "Select", options: "Low\nMedium\nHigh\nUrgent", default: "Medium" },
                { fieldtype: "Section Break", label: "Description" },
                { label: "Description", fieldname: "description", fieldtype: "Text Editor" },
            ],
            primary_action_label: "Create Task",
            primary_action: function(values) {
                frappe.call({
                    method: "gicore.gi_core.page.task_tracker_v2.task_tracker_v2_v2.create_task",
                    args: {
                        subject: values.subject,
                        project: values.project || "",
                        task_type: values.task_type || "",
                        priority: values.priority || "Medium",
                        description: values.description || "",
                    },
                    callback: function(r) {
                        frappe.show_alert({ message: `Task "${r.message.subject}" created.`, indicator: "green" }, 3);
                        d.hide();
                        reload();
                    },
                });
            },
        });
        d.show();
    }

    // ══════════════════════════════════════════════════════════════════════
    // Utility Functions
    // ══════════════════════════════════════════════════════════════════════
    function set_loading(on) {
        if (on) {
            $("#tt-task-list").html(`<div class="tt-empty"><i class="fa fa-spinner fa-spin fa-2x"></i></div>`);
        }
    }

    function escape_html(str) {
        if (!str) return "";
        return String(str).replace(/[&<>]/g, function(m) {
            if (m === '&') return '&amp;';
            if (m === '<') return '&lt;';
            if (m === '>') return '&gt;';
            return m;
        });
    }

    function status_options(current) {
        const opts = ["Open", "Working", "Pending Review", "Overdue", "Cancelled", "Completed"];
        return opts.map(s => `<option value="${s}" ${s === current ? "selected" : ""}>${s}</option>`).join("");
    }

    function progress_color(pct) {
        if (pct >= 100) return "#3B6D11";
        if (pct >= 60) return "#1D9E75";
        if (pct >= 30) return "#BA7517";
        return "#A32D2D";
    }
};

// Update HTML template with separate sections for stats
const TT_HTML = `
<div id="tt-root">
    <!-- Status Stats Section -->
    <div class="tt-stats-section">
        <div class="tt-stats-title">
            <i class="fa fa-chart-simple"></i> Status
        </div>
        <div id="tt-stats-status" class="tt-stats-bar"></div>
    </div>

    <!-- Task Type Stats Section -->
    <div id="tt-stats-type-section" class="tt-stats-section" style="display: none;">
        <div class="tt-stats-title">
            <i class="fa fa-tags"></i> Task Types
        </div>
        <div id="tt-stats-type" class="tt-stats-bar"></div>
    </div>

    <!-- Priority Stats Section -->
    <div class="tt-stats-section">
        <div class="tt-stats-title">
            <i class="fa fa-flag"></i> Priority
        </div>
        <div id="tt-stats-priority" class="tt-stats-bar"></div>
    </div>

    <!-- Filter bar -->
    <div class="tt-filter-bar">
        <div class="tt-search-wrap">
            <i class="fa fa-search tt-search-icon"></i>
            <input id="tt-search" type="text" placeholder="Search tasks..." class="tt-search-input" />
        </div>
        <select id="tt-filter-project" class="tt-select">
            <option value="">All Projects</option>
        </select>
        <select id="tt-filter-type" class="tt-select">
            <option value="">All Types</option>
        </select>
        <select id="tt-filter-status" class="tt-select">
            <option value="">All Statuses</option>
            <option value="Open">Open</option>
            <option value="Working">Working</option>
            <option value="Pending Review">Pending Review</option>
            <option value="Overdue">Overdue</option>
            <option value="Cancelled">Cancelled</option>
            <option value="Completed">Completed</option>
        </select>
        <select id="tt-filter-priority" class="tt-select">
            <option value="">All Priorities</option>
            <option value="Low">Low</option>
            <option value="Medium">Medium</option>
            <option value="High">High</option>
            <option value="Urgent">Urgent</option>
        </select>
        <button id="tt-clear-filters" class="tt-btn-ghost">
            <i class="fa fa-times"></i> Clear
        </button>
    </div>

    <!-- Task list -->
    <div id="tt-task-list" class="tt-task-list"></div>

    <!-- Pagination -->
    <div id="tt-pagination" class="tt-pagination"></div>

    <!-- Overlay -->
    <div id="tt-overlay" class="tt-overlay"></div>

    <!-- Review Panel -->
    <div id="tt-review-panel" class="tt-review-panel">
        <div class="tt-panel-topbar">
            <h4>Task Details</h4>
            <button id="tt-panel-close" class="tt-panel-close">×</button>
        </div>
        <div id="tt-panel-body" class="tt-panel-body"></div>
    </div>
</div>
`;

// Add these CSS additions to your TT_CSS
const additionalCSS = `
.tt-stats-section {
    margin-bottom: 24px;
}
.tt-stats-title {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    color: var(--text-muted);
    margin-bottom: 12px;
    letter-spacing: 0.5px;
    display: flex;
    align-items: center;
    gap: 6px;
}
.tt-stats-title i {
    font-size: 12px;
}
.tt-stat-type {
    background: linear-gradient(135deg, var(--card-bg) 0%, var(--control-bg) 100%);
}
.tt-pri-low-card .tt-stat-val { color: #2E7D32; }
.tt-pri-low-card { border-left: 3px solid #2E7D32; }
.tt-pri-medium-card .tt-stat-val { color: #E65100; }
.tt-pri-medium-card { border-left: 3px solid #E65100; }
.tt-pri-high-card .tt-stat-val { color: #C62828; }
.tt-pri-high-card { border-left: 3px solid #C62828; }
.tt-pri-urgent-card .tt-stat-val { color: #C2185B; }
.tt-pri-urgent-card { border-left: 3px solid #C2185B; }
.tt-stat-active {
    background: var(--primary-light);
    border-color: var(--primary);
    transform: scale(1.02);
}
`;

// Append to your existing TT_CSS

// CSS styles (add panel field styles)
const TT_CSS = `
#tt-root { padding: 20px; max-width: 1400px; margin: 0 auto; }
.tt-stats-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 12px; margin-bottom: 24px; }
.tt-stat { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; cursor: pointer; transition: all 0.2s; }
.tt-stat:hover { transform: translateY(-2px); box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
.tt-stat-icon { font-size: 24px; opacity: 0.7; }
.tt-stat-val { font-size: 24px; font-weight: 700; line-height: 1.2; }
.tt-stat-lbl { font-size: 11px; color: var(--text-muted); text-transform: uppercase; }
.tt-stat-open .tt-stat-val { color: #1D9E75; }
.tt-stat-working .tt-stat-val { color: #378ADD; }
.tt-stat-overdue .tt-stat-val { color: #E24B4A; }
.tt-stat-completed .tt-stat-val { color: #639922; }

.tt-filter-bar { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 24px; padding: 12px; background: var(--control-bg); border-radius: 8px; }
.tt-search-wrap { flex: 2; min-width: 200px; position: relative; }
.tt-search-input { width: 100%; padding: 8px 12px 8px 32px; border: 1px solid var(--border-color); border-radius: 6px; }
.tt-search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); }
.tt-select { padding: 8px 12px; border: 1px solid var(--border-color); border-radius: 6px; min-width: 120px; }
.tt-btn-ghost { padding: 8px 16px; border: 1px solid var(--border-color); border-radius: 6px; background: var(--bg-color); cursor: pointer; }
.tt-btn-ghost:hover { background: var(--primary); color: white; }

.tt-grid-view { display: grid; grid-template-columns: repeat(auto-fill, minmax(300px, 1fr)); gap: 16px; }
.tt-card-grid { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; padding: 12px; cursor: pointer; transition: all 0.2s; }
.tt-card-grid:hover { transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,0.1); border-color: var(--primary); }
.tt-grid-header { display: flex; justify-content: space-between; margin-bottom: 8px; }
.tt-priority-badge { padding: 2px 8px; border-radius: 12px; font-size: 11px; font-weight: 600; }
.tt-pri-low { background: #E8F5E9; color: #2E7D32; }
.tt-pri-medium { background: #FFF3E0; color: #E65100; }
.tt-pri-high { background: #FFEBEE; color: #C62828; }
.tt-pri-urgent { background: #FCE4EC; color: #C2185B; }
.tt-badge-sm { padding: 2px 6px; border-radius: 10px; font-size: 10px; font-weight: 600; }
.tt-grid-title { font-size: 13px; font-weight: 600; margin-bottom: 8px; line-height: 1.4; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; }
.tt-grid-meta { display: flex; gap: 8px; font-size: 11px; color: var(--text-muted); margin-bottom: 8px; flex-wrap: wrap; }
.tt-progress-compact { display: flex; align-items: center; gap: 8px; margin-bottom: 8px; }
.tt-progress-bar { flex: 1; height: 4px; background: var(--border-color); border-radius: 2px; overflow: hidden; }
.tt-progress-fill { height: 100%; transition: width 0.3s; }
.tt-progress-pct { font-size: 10px; min-width: 35px; }
.tt-grid-actions { display: flex; gap: 6px; }
.tt-status-select { flex: 1; padding: 4px; font-size: 11px; border: 1px solid var(--border-color); border-radius: 4px; }
.tt-icon-btn { padding: 4px 6px; border: 1px solid var(--border-color); border-radius: 4px; background: transparent; cursor: pointer; }

.tt-list-view { display: flex; flex-direction: column; gap: 6px; }
.tt-card-compact { display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 6px; cursor: pointer; }
.tt-card-compact:hover { background: var(--control-bg); border-color: var(--primary); }
.tt-compact-priority { flex-shrink: 0; }
.tt-priority-dot { width: 8px; height: 8px; border-radius: 50%; display: block; }
.tt-compact-info { flex: 1; min-width: 0; }
.tt-compact-title { font-size: 12px; font-weight: 500; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.tt-compact-meta { display: flex; gap: 8px; font-size: 10px; color: var(--text-muted); margin-bottom: 4px; flex-wrap: wrap; }
.tt-progress-tiny { width: 100px; }
.tt-compact-status { display: flex; align-items: center; gap: 8px; flex-shrink: 0; }
.tt-status-select-sm { padding: 2px 4px; font-size: 10px; border: 1px solid var(--border-color); border-radius: 3px; }
.tt-icon-btn-sm { padding: 2px 6px; border: 1px solid var(--border-color); border-radius: 3px; background: transparent; cursor: pointer; font-size: 10px; }
.tt-icon-btn-sm:hover { color: var(--primary); border-color: var(--primary); }

.tt-pagination-wrapper { display: flex; justify-content: space-between; align-items: center; margin-top: 24px; padding-top: 16px; border-top: 1px solid var(--border-color); }
.tt-pag-info { font-size: 12px; color: var(--text-muted); }
.tt-pag-controls { display: flex; gap: 8px; }
.tt-pag-btn { padding: 6px 12px; border: 1px solid var(--border-color); border-radius: 4px; background: var(--card-bg); cursor: pointer; font-size: 12px; }
.tt-pag-btn:hover { background: var(--primary); color: white; }

.tt-overlay { display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.5); z-index: 1040; }
.tt-overlay-active { display: block; }
.tt-review-panel { position: fixed; top: 0; right: 0; width: 480px; max-width: 90vw; height: 100vh; background: var(--card-bg); z-index: 1050; transform: translateX(100%); transition: transform 0.25s; display: flex; flex-direction: column; box-shadow: -2px 0 8px rgba(0,0,0,0.1); }
.tt-panel-open { transform: translateX(0); }
.tt-panel-topbar { display: flex; justify-content: space-between; align-items: center; padding: 16px 20px; border-bottom: 1px solid var(--border-color); background: var(--card-bg); }
.tt-panel-topbar h4 { margin: 0; font-size: 16px; font-weight: 600; }
.tt-panel-close { background: none; border: none; font-size: 24px; cursor: pointer; color: var(--text-muted); line-height: 1; padding: 0 8px; }
.tt-panel-close:hover { color: var(--text-color); }
.tt-panel-body { flex: 1; overflow-y: auto; padding: 20px; }
.tt-panel-header { margin-bottom: 20px; }
.tt-panel-header h3 { margin: 0 0 10px 0; font-size: 18px; font-weight: 600; }
.tt-panel-meta { display: flex; gap: 10px; margin-top: 8px; flex-wrap: wrap; }
.tt-panel-details { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 20px; }
.tt-detail-row { display: flex; justify-content: space-between; font-size: 13px; padding: 6px 0; border-bottom: 1px solid var(--border-color); }
.tt-detail-row label { font-weight: 600; color: var(--text-muted); }
.tt-progress-bar-lg { height: 8px; margin-bottom: 20px; }
.tt-panel-field { margin-bottom: 20px; }
.tt-panel-field label { font-weight: 600; color: var(--text-muted); display: block; margin-bottom: 5px; font-size: 12px; text-transform: uppercase; }
.tt-panel-desc { margin-bottom: 20px; }
.tt-panel-desc label { font-weight: 600; display: block; margin-bottom: 8px; font-size: 12px; text-transform: uppercase; color: var(--text-muted); }
.tt-panel-desc div { font-size: 13px; line-height: 1.5; }
.tt-panel-comments label { font-weight: 600; display: block; margin-bottom: 8px; font-size: 12px; text-transform: uppercase; color: var(--text-muted); }
.tt-comment { padding: 8px 12px; background: var(--control-bg); border-radius: 6px; margin-bottom: 8px; }
.tt-comment-meta { display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 4px; color: var(--text-muted); }
.tt-comment-body { font-size: 12px; line-height: 1.4; }
.tt-add-comment textarea { font-family: inherit; font-size: 12px; resize: vertical; }
.tt-panel-actions { margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border-color); }
.tt-btn-primary { padding: 8px 16px; background: var(--primary); color: white; border: none; border-radius: 6px; cursor: pointer; width: 100%; font-size: 13px; font-weight: 500; }
.tt-btn-primary:hover { opacity: 0.9; }
.tt-empty { text-align: center; padding: 60px 20px; color: var(--text-muted); }
.tt-empty i { font-size: 48px; margin-bottom: 16px; display: block; }
.tt-btn-link { background: none; border: none; color: var(--primary); cursor: pointer; margin-top: 12px; text-decoration: underline; }

.tt-status-open { background: #E1F5EE; color: #0F6E56; }
.tt-status-working { background: #E6F1FB; color: #185FA5; }
.tt-status-pending-review { background: #FAEEDA; color: #854F0B; }
.tt-status-overdue { background: #FCEBEB; color: #A32D2D; }
.tt-status-completed { background: #EAF3DE; color: #3B6D11; }

@media (max-width: 768px) {
    #tt-root { padding: 12px; }
    .tt-grid-view { grid-template-columns: 1fr; }
    .tt-filter-bar .tt-select { min-width: 100px; }
    .tt-review-panel { width: 100vw; }
}
`;

// Add this backend method to your task_tracker.py file
// def add_comment(task_name, comment):
//     task = frappe.get_doc("Task", task_name)
//     task.add_comment(text=comment)
//     return {"success": True}