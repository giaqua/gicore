/**
 * task_tracker.js
 *
 * Place at: <your_app>/page/task_tracker/task_tracker.js
 *
 * Frappe Page controller for the Task Tracker.
 * Handles: filter bar, task grid/list, quick-review slide panel,
 *          add-task dialog, inline status updates, pagination.
 */

frappe.pages["task-tracker"].on_page_load = function (wrapper) {
    const page = frappe.ui.make_app_page({
        parent: wrapper,
        title:  "Task Tracker",
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
        search:    "",
        project:   "",
        task_type: "",
        status:    "",
        page:      1,
        page_size: 50,
        tasks:     [],
        total:     0,
        loading:   false,
    };

    // ── Populate filter dropdowns ──────────────────────────────────────────
    frappe.call({
        method: "gicore.gi_core.page.task_tracker.task_tracker.get_filter_options",
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

    // ── Filter events ──────────────────────────────────────────────────────
    let search_timer;
    $("#tt-search").on("input", function () {
        clearTimeout(search_timer);
        search_timer = setTimeout(() => {
            state.search = this.value.trim();
            state.page   = 1;
            load();
        }, 320);
    });

    ["#tt-filter-project", "#tt-filter-type", "#tt-filter-status"].forEach(sel => {
        $(sel).on("change", function () {
            if (sel === "#tt-filter-project") state.project   = this.value;
            if (sel === "#tt-filter-type")    state.task_type = this.value;
            if (sel === "#tt-filter-status")  state.status    = this.value;
            state.page = 1;
            load();
        });
    });

    $("#tt-clear-filters").on("click", () => {
        state.search = state.project = state.task_type = state.status = "";
        state.page = 1;
        $("#tt-search").val("");
        $("#tt-filter-project, #tt-filter-type, #tt-filter-status").val("");
        load();
    });

    // ── Close review panel ─────────────────────────────────────────────────
    $(document).on("click", "#tt-panel-close, #tt-overlay", () => close_panel());

    // ── Initial load ───────────────────────────────────────────────────────
    load();

    // ══════════════════════════════════════════════════════════════════════
    // Core load function
    // ══════════════════════════════════════════════════════════════════════
    function load() {
        if (state.loading) return;
        state.loading = true;
        set_loading(true);

        frappe.call({
            method: "gicore.gi_core.page.task_tracker.task_tracker.get_tasks",
            args: {
                search:    state.search,
                project:   state.project,
                task_type: state.task_type,
                status:    state.status,
                page:      state.page,
                page_size: state.page_size,
            },
            callback: function (r) {
                state.loading = false;
                set_loading(false);
                const { tasks, total, counts } = r.message;
                state.tasks = tasks;
                state.total = total;

                render_stat_bar(counts);
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
    // Render helpers
    // ══════════════════════════════════════════════════════════════════════
    function render_stat_bar(counts) {
        const items = [
            { label: "Total",     value: counts.total,     cls: "tt-stat-total"     },
            { label: "Open",      value: counts.open,      cls: "tt-stat-open"      },
            { label: "Working",   value: counts.working,   cls: "tt-stat-working"   },
            { label: "Overdue",   value: counts.overdue,   cls: "tt-stat-overdue"   },
            { label: "Completed", value: counts.completed, cls: "tt-stat-completed" },
        ];
        $("#tt-stats").html(
            items.map(i =>
                `<div class="tt-stat ${i.cls}">
                    <span class="tt-stat-val">${i.value}</span>
                    <span class="tt-stat-lbl">${i.label}</span>
                </div>`
            ).join("")
        );
    }

    function render_tasks(tasks, state) {
        const $list = $("#tt-task-list");

        if (!tasks.length) {
            $list.html(
                `<div class="tt-empty">
                    <i class="fa fa-inbox"></i>
                    <p>No tasks match your filters.</p>
                    <button class="tt-btn-link" id="tt-clear-filters-empty">Clear filters</button>
                </div>`
            );
            $("#tt-clear-filters-empty").on("click", () => $("#tt-clear-filters").trigger("click"));
            return;
        }

        const rows = tasks.map(t => {
            const due_str   = t.exp_end_date
                ? frappe.datetime.str_to_user(t.exp_end_date)
                : "—";
            const overdue   = t.exp_end_date
                && frappe.datetime.get_diff(frappe.datetime.nowdate(), t.exp_end_date) > 0
                && t.status !== "Completed"
                && t.status !== "Cancelled";
            const pct       = parseInt(t.progress || 0);
            const pri_cls   = `tt-pri-${(t.priority || "medium").toLowerCase()}`;
            const stat_cls  = `tt-status-${(t.status || "open").toLowerCase().replace(/ /g, "-")}`;

            return `
            <div class="tt-card" data-task="${t.name}" tabindex="0" role="button"
                 aria-label="Review task: ${escape_html(t.subject || t.name)}">
                <div class="tt-card-left">
                    <span class="tt-priority-dot ${pri_cls}" title="${t.priority || 'Medium'} priority"></span>
                </div>
                <div class="tt-card-body">
                    <div class="tt-card-top">
                        <span class="tt-card-subject">${escape_html(t.subject || t.name)}</span>
                        <span class="tt-badge ${stat_cls}">${t.status || "Open"}</span>
                    </div>
                    <div class="tt-card-meta">
                        ${t.project
                            ? `<span class="tt-meta-item"><i class="fa fa-folder-o"></i> ${escape_html(t.project)}</span>`
                            : ""}
                        ${t.type
                            ? `<span class="tt-meta-item"><i class="fa fa-tag"></i> ${escape_html(t.type)}</span>`
                            : ""}
                        ${t.assignee
                            ? `<span class="tt-meta-item"><i class="fa fa-user-o"></i> ${escape_html(t.assignee)}</span>`
                            : ""}
                        <span class="tt-meta-item ${overdue ? "tt-overdue-date" : ""}">
                            <i class="fa fa-calendar-o"></i> ${due_str}
                        </span>
                    </div>
                    <div class="tt-progress-row">
                        <div class="tt-progress-bar">
                            <div class="tt-progress-fill" style="width:${pct}%;background:${progress_color(pct)};"></div>
                        </div>
                        <span class="tt-progress-label">${pct}%</span>
                    </div>
                </div>
                <div class="tt-card-actions">
                    <select class="tt-inline-status" data-task="${t.name}" title="Change status"
                            onclick="event.stopPropagation()">
                        ${status_options(t.status)}
                    </select>
                    <button class="tt-btn-open" data-task="${t.name}" title="Open full form"
                            onclick="event.stopPropagation()">
                        <i class="fa fa-external-link"></i>
                    </button>
                </div>
            </div>`;
        }).join("");

        $list.html(rows);

        // Click card → open review panel
        $list.find(".tt-card").on("click keydown", function (e) {
            if (e.type === "keydown" && e.key !== "Enter") return;
            open_review_panel($(this).data("task"));
        });

        // Open full form
        $list.find(".tt-btn-open").on("click", function () {
            frappe.set_route("Form", "Task", $(this).data("task"));
        });

        // Inline status change
        $list.find(".tt-inline-status").on("change", function () {
            const $sel       = $(this);
            const task_name  = $sel.data("task");
            const new_status = $sel.val();

            frappe.call({
                method: "gicore.gi_core.page.task_tracker.task_tracker.update_task_status",
                args: { task_name, status: new_status },
                callback: function () {
                    frappe.show_alert(
                        { message: `Status → <b>${new_status}</b>`, indicator: "green" }, 3
                    );
                    // Update badge in card without full reload
                    const $card  = $sel.closest(".tt-card");
                    const stat_cls = `tt-status-${new_status.toLowerCase().replace(/ /g, "-")}`;
                    const all_stat = [
                        "tt-status-open","tt-status-working","tt-status-pending-review",
                        "tt-status-overdue","tt-status-cancelled","tt-status-completed",
                    ];
                    $card.find(".tt-badge")
                        .removeClass(all_stat.join(" "))
                        .addClass(stat_cls)
                        .text(new_status);

                    // Refresh stat bar quietly
                    frappe.call({
                        method: "gicore.gi_core.page.task_tracker.task_tracker.get_tasks",
                        args: { ...state_args(), page: 1, page_size: 1 },
                        callback: function (r) { render_stat_bar(r.message.counts); },
                    });
                },
            });
        });
    }

    function render_pagination(total, state) {
        const pages = Math.ceil(total / state.page_size);
        const $pag  = $("#tt-pagination");
        if (pages <= 1) { $pag.html(""); return; }

        let html = `<span class="tt-pag-info">Page ${state.page} of ${pages} (${total} tasks)</span>`;
        if (state.page > 1)
            html += `<button class="tt-pag-btn" id="tt-prev">‹ Prev</button>`;
        if (state.page < pages)
            html += `<button class="tt-pag-btn" id="tt-next">Next ›</button>`;

        $pag.html(html);
        $("#tt-prev").on("click", () => { state.page--; load(); });
        $("#tt-next").on("click", () => { state.page++; load(); });
    }

    // ══════════════════════════════════════════════════════════════════════
    // Quick-review slide panel
    // ══════════════════════════════════════════════════════════════════════
    function open_review_panel(task_name) {
        const $panel = $("#tt-review-panel");
        $panel.find("#tt-panel-body").html(
            `<div class="tt-panel-loading"><i class="fa fa-spinner fa-spin"></i> Loading…</div>`
        );
        $panel.addClass("tt-panel-open");
        $("#tt-overlay").addClass("tt-overlay-active");

        frappe.call({
            method: "gicore.gi_core.page.task_tracker.task_tracker.get_task_detail",
            args: { task_name },
            callback: function (r) {
                const t = r.message;
                const pct = parseInt(t.progress || 0);

                const comments_html = t.comments.length
                    ? t.comments.map(c =>
                        `<div class="tt-comment">
                            <div class="tt-comment-meta">
                                <b>${escape_html(c.comment_by)}</b>
                                <span>${frappe.datetime.str_to_user(c.creation)}</span>
                            </div>
                            <div class="tt-comment-body">${c.content}</div>
                        </div>`
                    ).join("")
                    : `<p class="tt-muted">No comments yet.</p>`;

                $panel.find("#tt-panel-body").html(`
                    <div class="tt-panel-header-block">
                        <div class="tt-panel-title">${escape_html(t.subject)}</div>
                        <div class="tt-panel-sub">
                            <span class="tt-badge tt-status-${(t.status||"open").toLowerCase().replace(/ /g,"-")}">${t.status}</span>
                            ${t.project ? `<span class="tt-meta-item"><i class="fa fa-folder-o"></i> ${escape_html(t.project)}</span>` : ""}
                            ${t.type    ? `<span class="tt-meta-item"><i class="fa fa-tag"></i> ${escape_html(t.type)}</span>`    : ""}
                        </div>
                    </div>

                    <div class="tt-panel-section">
                        <div class="tt-kv-grid">
                            <div class="tt-kv"><span>Priority</span><b>${t.priority || "—"}</b></div>
                            <div class="tt-kv"><span>Start</span><b>${t.exp_start_date || "—"}</b></div>
                            <div class="tt-kv"><span>Due</span><b>${t.exp_end_date || "—"}</b></div>
                            <div class="tt-kv"><span>Parent task</span><b>${escape_html(t.parent_task || "—")}</b></div>
                            <div class="tt-kv"><span>Assigned to</span>
                                <b>${t.assignees.length ? t.assignees.join(", ") : "—"}</b>
                            </div>
                        </div>
                    </div>

                    <div class="tt-panel-section">
                        <div class="tt-panel-label">Progress</div>
                        <div class="tt-progress-row">
                            <div class="tt-progress-bar tt-progress-bar-lg">
                                <div class="tt-progress-fill" style="width:${pct}%;background:${progress_color(pct)};"></div>
                            </div>
                            <span class="tt-progress-label">${pct}%</span>
                        </div>
                    </div>

                    ${t.description ? `
                    <div class="tt-panel-section">
                        <div class="tt-panel-label">Description</div>
                        <div class="tt-description">${t.description}</div>
                    </div>` : ""}

                    <div class="tt-panel-section">
                        <div class="tt-panel-label">Comments</div>
                        <div class="tt-comments">${comments_html}</div>
                    </div>

                    <div class="tt-panel-footer">
                        <button class="tt-btn-primary tt-btn-open-full" data-task="${t.name}">
                            <i class="fa fa-external-link"></i> Open full form
                        </button>
                    </div>
                `);

                $panel.find(".tt-btn-open-full").on("click", function () {
                    frappe.set_route("Form", "Task", $(this).data("task"));
                });
            },
        });
    }

    function close_panel() {
        $("#tt-review-panel").removeClass("tt-panel-open");
        $("#tt-overlay").removeClass("tt-overlay-active");
    }

    // ══════════════════════════════════════════════════════════════════════
    // Add Task dialog
    // ══════════════════════════════════════════════════════════════════════
    function open_add_dialog(state, reload) {
        const d = new frappe.ui.Dialog({
            title: "New Task",
            fields: [
                {
                    label:     "Subject",
                    fieldname: "subject",
                    fieldtype: "Data",
                    reqd:      1,
                },
                {
                    label:     "Project",
                    fieldname: "project",
                    fieldtype: "Link",
                    options:   "Project",
                    default:   state.project || "",
                },
                {
                    fieldtype: "Column Break",
                },
                {
                    label:     "Task Type",
                    fieldname: "task_type",
                    fieldtype: "Data",
                    default:   state.task_type || "",
                },
                {
                    label:     "Priority",
                    fieldname: "priority",
                    fieldtype: "Select",
                    options:   "Low\nMedium\nHigh\nUrgent",
                    default:   "Medium",
                },
                {
                    fieldtype: "Section Break",
                    label:     "Description",
                },
                {
                    label:     "Description",
                    fieldname: "description",
                    fieldtype: "Text Editor",
                },
            ],
            primary_action_label: "Create Task",
            primary_action: function (values) {
                frappe.call({
                    method: "gicore.gi_core.page.task_tracker.task_tracker.create_task",
                    args: {
                        subject:     values.subject,
                        project:     values.project || "",
                        task_type:   values.task_type || "",
                        priority:    values.priority || "Medium",
                        description: values.description || "",
                    },
                    callback: function (r) {
                        frappe.show_alert(
                            { message: `Task <b>${r.message.subject}</b> created.`, indicator: "green" }, 4
                        );
                        d.hide();
                        reload();
                    },
                });
            },
        });
        d.show();
    }

    // ══════════════════════════════════════════════════════════════════════
    // Utility
    // ══════════════════════════════════════════════════════════════════════
    function set_loading(on) {
        if (on) {
            $("#tt-task-list").html(
                `<div class="tt-empty"><i class="fa fa-spinner fa-spin fa-2x"></i></div>`
            );
        }
    }

    function state_args() {
        return {
            search:    state.search,
            project:   state.project,
            task_type: state.task_type,
            status:    state.status,
            page:      state.page,
            page_size: state.page_size,
        };
    }

    function escape_html(str) {
        if (!str) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    function status_options(current) {
        const opts = ["Open","Working","Pending Review","Overdue","Cancelled","Completed"];
        return opts.map(s =>
            `<option value="${s}" ${s === current ? "selected" : ""}>${s}</option>`
        ).join("");
    }

    function progress_color(pct) {
        if (pct >= 100) return "#3B6D11";
        if (pct  >= 60) return "#1D9E75";
        if (pct  >= 30) return "#BA7517";
        return "#A32D2D";
    }
};


// ════════════════════════════════════════════════════════════════════════════
// Embedded HTML template
// ════════════════════════════════════════════════════════════════════════════
const TT_HTML = `
<div id="tt-root">

    <!-- Stat bar -->
    <div id="tt-stats" class="tt-stats-bar"></div>

    <!-- Filter bar -->
    <div class="tt-filter-bar">
        <div class="tt-search-wrap">
            <i class="fa fa-search tt-search-icon"></i>
            <input id="tt-search" type="text" placeholder="Search tasks…" class="tt-search-input" />
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
        <button id="tt-clear-filters" class="tt-btn-ghost" title="Clear all filters">
            <i class="fa fa-times"></i> Clear
        </button>
    </div>

    <!-- Task list -->
    <div id="tt-task-list" class="tt-task-list"></div>

    <!-- Pagination -->
    <div id="tt-pagination" class="tt-pagination"></div>

    <!-- Overlay -->
    <div id="tt-overlay" class="tt-overlay"></div>

    <!-- Quick-review slide panel -->
    <div id="tt-review-panel" class="tt-review-panel" role="dialog" aria-label="Task details">
        <div class="tt-panel-topbar">
            <span class="tt-panel-eyebrow">Task detail</span>
            <button id="tt-panel-close" class="tt-panel-close" aria-label="Close">
                <i class="fa fa-times"></i>
            </button>
        </div>
        <div id="tt-panel-body" class="tt-panel-body"></div>
    </div>

</div>
`;


// ════════════════════════════════════════════════════════════════════════════
// Embedded CSS
// ════════════════════════════════════════════════════════════════════════════
const TT_CSS = `
/* ── Root ───────────────────────────────────────────── */
#tt-root {
    padding: 0 0 60px;
    font-family: var(--font-stack);
    position: relative;
}

/* ── Stat bar ───────────────────────────────────────── */
.tt-stats-bar {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 18px;
}
.tt-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 12px 20px;
    border-radius: 8px;
    border: 1px solid var(--border-color);
    background: var(--card-bg);
    min-width: 90px;
    cursor: default;
}
.tt-stat-val { font-size: 22px; font-weight: 700; line-height: 1.1; }
.tt-stat-lbl { font-size: 11px; color: var(--text-muted); margin-top: 2px; text-transform: uppercase; letter-spacing:.04em; }

.tt-stat-open      .tt-stat-val { color: #1D9E75; }
.tt-stat-working   .tt-stat-val { color: #378ADD; }
.tt-stat-overdue   .tt-stat-val { color: #E24B4A; }
.tt-stat-completed .tt-stat-val { color: #639922; }

/* ── Filter bar ─────────────────────────────────────── */
.tt-filter-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-bottom: 16px;
}
.tt-search-wrap {
    position: relative;
    flex: 1;
    min-width: 180px;
}
.tt-search-icon {
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 13px;
    pointer-events: none;
}
.tt-search-input {
    width: 100%;
    padding: 7px 10px 7px 30px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--control-bg);
    color: var(--text-color);
    font-size: 13px;
    outline: none;
    box-sizing: border-box;
}
.tt-search-input:focus { border-color: var(--primary); }

.tt-select {
    padding: 7px 10px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--control-bg);
    color: var(--text-color);
    font-size: 13px;
    cursor: pointer;
    min-width: 140px;
}
.tt-select:focus { outline: none; border-color: var(--primary); }

.tt-btn-ghost {
    padding: 7px 12px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: transparent;
    color: var(--text-muted);
    font-size: 13px;
    cursor: pointer;
    white-space: nowrap;
}
.tt-btn-ghost:hover { background: var(--control-bg); color: var(--text-color); }

/* ── Task cards ─────────────────────────────────────── */
.tt-task-list { display: flex; flex-direction: column; gap: 8px; }

.tt-card {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border: 1px solid var(--border-color);
    border-radius: 8px;
    background: var(--card-bg);
    cursor: pointer;
    transition: border-color .15s, box-shadow .15s;
}
.tt-card:hover { border-color: var(--primary); box-shadow: 0 2px 8px rgba(0,0,0,.06); }
.tt-card:focus { outline: 2px solid var(--primary); }

.tt-card-left { flex-shrink: 0; }
.tt-priority-dot {
    display: block;
    width: 10px; height: 10px;
    border-radius: 50%;
}
.tt-pri-low    { background: #9FE1CB; }
.tt-pri-medium { background: #FAC775; }
.tt-pri-high   { background: #F0997B; }
.tt-pri-urgent { background: #E24B4A; }

.tt-card-body   { flex: 1; min-width: 0; }
.tt-card-top    { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; flex-wrap: wrap; }
.tt-card-subject { font-size: 14px; font-weight: 600; color: var(--text-color); flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

.tt-card-meta {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin-bottom: 6px;
}
.tt-meta-item { font-size: 12px; color: var(--text-muted); display: flex; align-items: center; gap: 4px; }
.tt-meta-item i { font-size: 11px; }
.tt-overdue-date { color: #E24B4A !important; font-weight: 600; }

/* ── Progress bar ───────────────────────────────────── */
.tt-progress-row { display: flex; align-items: center; gap: 8px; }
.tt-progress-bar { flex: 1; background: var(--border-color); border-radius: 4px; height: 6px; overflow: hidden; }
.tt-progress-bar-lg { height: 10px; border-radius: 6px; }
.tt-progress-fill { height: 100%; border-radius: 4px; transition: width .3s; }
.tt-progress-label { font-size: 11px; color: var(--text-muted); min-width: 28px; text-align: right; }

/* ── Card actions ───────────────────────────────────── */
.tt-card-actions { display: flex; flex-direction: column; gap: 6px; align-items: flex-end; flex-shrink: 0; }

.tt-inline-status {
    font-size: 12px;
    padding: 4px 6px;
    border: 1px solid var(--border-color);
    border-radius: 5px;
    background: var(--control-bg);
    color: var(--text-color);
    cursor: pointer;
    max-width: 140px;
}
.tt-btn-open {
    background: transparent;
    border: 1px solid var(--border-color);
    border-radius: 5px;
    padding: 4px 8px;
    cursor: pointer;
    color: var(--text-muted);
    font-size: 12px;
}
.tt-btn-open:hover { color: var(--primary); border-color: var(--primary); }

/* ── Status badges ──────────────────────────────────── */
.tt-badge {
    display: inline-block;
    padding: 2px 9px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 600;
    white-space: nowrap;
    letter-spacing:.02em;
}
.tt-status-open           { background:#E1F5EE; color:#0F6E56; }
.tt-status-working        { background:#E6F1FB; color:#185FA5; }
.tt-status-pending-review { background:#FAEEDA; color:#854F0B; }
.tt-status-overdue        { background:#FCEBEB; color:#A32D2D; }
.tt-status-cancelled      { background:#F1EFE8; color:#5F5E5A; }
.tt-status-completed      { background:#EAF3DE; color:#3B6D11; }

/* ── Empty / loading state ──────────────────────────── */
.tt-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 60px 20px;
    color: var(--text-muted);
    gap: 10px;
}
.tt-empty i { font-size: 32px; }
.tt-btn-link { background: none; border: none; color: var(--primary); cursor: pointer; font-size: 14px; text-decoration: underline; }

/* ── Pagination ─────────────────────────────────────── */
.tt-pagination {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-top: 18px;
    justify-content: center;
    font-size: 13px;
}
.tt-pag-info { color: var(--text-muted); }
.tt-pag-btn {
    padding: 6px 14px;
    border: 1px solid var(--border-color);
    border-radius: 6px;
    background: var(--card-bg);
    cursor: pointer;
    font-size: 13px;
}
.tt-pag-btn:hover { border-color: var(--primary); color: var(--primary); }

/* ── Overlay ─────────────────────────────────────────── */
.tt-overlay {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.35);
    z-index: 1040;
}
.tt-overlay-active { display: block; }

/* ── Review slide panel ─────────────────────────────── */
.tt-review-panel {
    position: fixed;
    top: 0; right: 0;
    width: 420px;
    max-width: 96vw;
    height: 100vh;
    background: var(--card-bg);
    border-left: 1px solid var(--border-color);
    z-index: 1050;
    display: flex;
    flex-direction: column;
    transform: translateX(100%);
    transition: transform .25s cubic-bezier(.4,0,.2,1);
    overflow: hidden;
}
.tt-panel-open { transform: translateX(0); }

.tt-panel-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    border-bottom: 1px solid var(--border-color);
    flex-shrink: 0;
}
.tt-panel-eyebrow { font-size: 11px; text-transform: uppercase; letter-spacing:.06em; color: var(--text-muted); font-weight: 600; }
.tt-panel-close {
    background: transparent; border: none; cursor: pointer;
    color: var(--text-muted); font-size: 16px; padding: 4px 6px; border-radius: 4px;
}
.tt-panel-close:hover { background: var(--control-bg); color: var(--text-color); }

.tt-panel-body { flex: 1; overflow-y: auto; padding: 18px; }
.tt-panel-loading { display: flex; align-items: center; justify-content: center; height: 120px; color: var(--text-muted); font-size: 18px; }

.tt-panel-header-block { margin-bottom: 16px; }
.tt-panel-title { font-size: 17px; font-weight: 700; color: var(--text-color); margin-bottom: 8px; line-height: 1.3; }
.tt-panel-sub   { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }

.tt-panel-section { margin-bottom: 20px; }
.tt-panel-label   { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing:.05em; color: var(--text-muted); margin-bottom: 8px; }

.tt-kv-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.tt-kv span { font-size: 11px; color: var(--text-muted); display: block; }
.tt-kv b    { font-size: 13px; font-weight: 600; color: var(--text-color); }

.tt-description { font-size: 13px; color: var(--text-color); line-height: 1.65; }
.tt-description * { max-width: 100%; }

.tt-comments { display: flex; flex-direction: column; gap: 10px; }
.tt-comment { padding: 10px 12px; background: var(--control-bg); border-radius: 6px; }
.tt-comment-meta { display: flex; justify-content: space-between; font-size: 11px; color: var(--text-muted); margin-bottom: 4px; }
.tt-comment-body { font-size: 13px; color: var(--text-color); line-height: 1.5; }

.tt-muted { color: var(--text-muted); font-size: 13px; }

.tt-panel-footer { padding-top: 16px; border-top: 1px solid var(--border-color); margin-top: 8px; }
.tt-btn-primary {
    display: inline-flex; align-items: center; gap: 6px;
    padding: 8px 16px; border-radius: 6px;
    background: var(--primary); color: #fff; border: none;
    font-size: 13px; font-weight: 600; cursor: pointer;
}
.tt-btn-primary:hover { opacity: .88; }

@media (max-width: 600px) {
    .tt-review-panel { width: 100vw; }
    .tt-card-actions { display: none; }
    .tt-stats-bar .tt-stat { min-width: 70px; padding: 10px 12px; }
}
`;
