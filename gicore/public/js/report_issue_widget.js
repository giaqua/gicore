// gicore/public/js/report_issue_widget.js

frappe.provide("gicore.issue");

gicore.issue._screenshot = null;
gicore.issue._attachments = []; // { file, name }

gicore.issue.render_fab = function () {
    const fab = document.createElement('div');
    fab.id = 'report-issue-fab';
    fab.innerHTML = `<svg width="15" height="15" fill="currentColor" viewBox="0 0 16 16">
        <path d="M8 15A7 7 0 1 0 8 1a7 7 0 0 0 0 14zm0 1A8 8 0 1 1 8 0a8 8 0 0 1 0 16z"/>
        <path d="M7.002 11a1 1 0 1 1 2 0 1 1 0 0 1-2 0zM7.1 4.995a.905.905 0 1 1 1.8 0l-.35 3.507a.552.552 0 0 1-1.1 0L7.1 4.995z"/>
    </svg> Report an Issue`;
    fab.style.cssText = `
        position: fixed; bottom: 24px; right: 24px;
        background: #D50000; color: white; padding: 10px 16px;
        border-radius: 24px; box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        cursor: pointer; z-index: 9998; font-size: 13px; font-weight: 500;
        display: flex; align-items: center; gap: 6px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        user-select: none;
    `;
    fab.onmouseenter = () => { fab.style.transform = 'scale(1.05)'; fab.style.boxShadow = '0 4px 14px rgba(0,0,0,0.35)'; };
    fab.onmouseleave = () => { fab.style.transform = 'scale(1)'; fab.style.boxShadow = '0 2px 10px rgba(0,0,0,0.3)'; };
    fab.addEventListener('click', () => gicore.issue.open());
    document.body.appendChild(fab);
};

// Opens the drawer immediately — no auto screenshot
gicore.issue.open = function () {
    gicore.issue.render_drawer();
};

// Called only when the user clicks "Take Screenshot" inside the drawer
gicore.issue.capture_screenshot = async function () {
    const btn = document.getElementById('gicore-screenshot-btn');
    if (!btn) return;
    const original_text = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = `<span class="gicore-spin"></span> Capturing...`;

    // Hide drawer + overlay + fab momentarily so they don't appear in the shot
    const drawer = document.getElementById('gicore-issue-drawer');
    const overlay = document.getElementById('gicore-issue-overlay');
    const fab = document.getElementById('report-issue-fab');
    const prev_drawer_display = drawer.style.display;
    drawer.style.display = 'none';
    overlay.style.display = 'none';
    if (fab) fab.style.display = 'none';

    let screenshot_data_url = null;
    try {
        if (typeof html2canvas !== 'undefined') {
            const canvas = await html2canvas(document.body, {
                scale: 0.75,
                logging: false,
                useCORS: true
            });
            screenshot_data_url = canvas.toDataURL('image/png');
        } else {
            frappe.show_alert({ message: 'Screenshot library not loaded', indicator: 'orange' }, 4);
        }
    } catch (e) {
        console.warn('Screenshot capture failed', e);
        frappe.show_alert({ message: 'Screenshot capture failed', indicator: 'red' }, 4);
    }

    drawer.style.display = prev_drawer_display || 'flex';
    overlay.style.display = 'block';
    if (fab) fab.style.display = 'flex';

    btn.disabled = false;
    btn.innerHTML = original_text;

    if (screenshot_data_url) {
        gicore.issue._screenshot = screenshot_data_url;
        gicore.issue._update_screenshot_preview(screenshot_data_url);
    }
};

gicore.issue._update_screenshot_preview = function (data_url) {
    const wrap = document.getElementById('gicore-screenshot-wrap');
    const img = document.getElementById('gicore-screenshot-img');
    const remove_link = document.getElementById('gicore-remove-shot');
    const take_btn = document.getElementById('gicore-screenshot-btn');
    if (!wrap) return;
    if (data_url) {
        img.src = data_url;
        wrap.style.display = 'block';
        remove_link.style.display = 'inline';
        take_btn.innerText = 'Retake Screenshot';
    } else {
        wrap.style.display = 'none';
        remove_link.style.display = 'none';
        take_btn.innerText = 'Take Screenshot';
    }
};

gicore.issue._render_attachments_list = function () {
    const list = document.getElementById('gicore-attachments-list');
    if (!list) return;
    if (!gicore.issue._attachments.length) {
        list.innerHTML = '';
        return;
    }
    list.innerHTML = gicore.issue._attachments.map((a, i) => `
        <div style="display:flex; justify-content:space-between; align-items:center; padding:4px 8px; background:#f6f7f8; border-radius:4px; margin-bottom:4px;">
            <span style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap; max-width:280px;">${a.name}</span>
            <span data-idx="${i}" class="gicore-remove-attachment" style="cursor:pointer; color:#D50000; font-weight:600; margin-left:8px;">&times;</span>
        </div>
    `).join('');
    list.querySelectorAll('.gicore-remove-attachment').forEach(el => {
        el.onclick = () => {
            gicore.issue._attachments.splice(parseInt(el.dataset.idx), 1);
            gicore.issue._render_attachments_list();
        };
    });
};

gicore.issue.render_drawer = function () {
    document.getElementById('gicore-issue-overlay')?.remove();
    document.getElementById('gicore-issue-drawer')?.remove();
    gicore.issue._screenshot = null;
    gicore.issue._attachments = [];

    const overlay = document.createElement('div');
    overlay.id = 'gicore-issue-overlay';
    overlay.style.cssText = `position: fixed; inset: 0; background: rgba(0,0,0,0.25); z-index: 9999; opacity: 0; transition: opacity 0.25s ease;`;
    overlay.onclick = gicore.issue.close;

    const drawer = document.createElement('div');
    drawer.id = 'gicore-issue-drawer';
    drawer.style.cssText = `
        position: fixed; top: 0; right: 0; height: 100vh; width: 420px;
        background: #fff; z-index: 10000; box-shadow: -4px 0 24px rgba(0,0,0,0.2);
        transform: translateX(100%); transition: transform 0.3s cubic-bezier(.2,.9,.3,1);
        display: flex; flex-direction: column; font-family: inherit;
    `;

    drawer.innerHTML = `
        <div style="padding: 16px 20px; border-bottom: 1px solid #eee; display:flex; justify-content:space-between; align-items:center;">
            <strong style="font-size:15px;">Report an Issue</strong>
            <span id="gicore-issue-close" style="cursor:pointer; font-size:20px; color:#888;">&times;</span>
        </div>
        <div style="flex:1; overflow-y:auto; padding: 16px 20px;">
            <label style="font-size:12px; font-weight:600; color:#555;">Subject *</label>
            <input id="gicore-subject" type="text" placeholder="Brief description" style="width:100%; padding:8px; margin:6px 0 14px; border:1px solid #d1d8dd; border-radius:6px; font-size:13px; box-sizing:border-box;">

            <label style="font-size:12px; font-weight:600; color:#555;">Priority</label>
            <select id="gicore-priority" style="width:100%; padding:8px; margin:6px 0 14px; border:1px solid #d1d8dd; border-radius:6px; font-size:13px; box-sizing:border-box;">
                <option>Low</option><option selected>Medium</option><option>High</option><option>Urgent</option>
            </select>

            <label style="font-size:12px; font-weight:600; color:#555;">Description *</label>
            <textarea id="gicore-description" rows="5" placeholder="What happened? What did you expect?" style="width:100%; padding:8px; margin:6px 0 14px; border:1px solid #d1d8dd; border-radius:6px; font-size:13px; resize:vertical; box-sizing:border-box;"></textarea>

            <label style="font-size:12px; font-weight:600; color:#555;">Screenshot (optional)</label>
            <div style="margin-top:6px;">
                <button id="gicore-screenshot-btn" type="button" style="background:#fff; border:1px solid #2490EF; color:#2490EF; padding:6px 12px; border-radius:6px; font-size:12px; cursor:pointer;">Take Screenshot</button>
            </div>
            <div id="gicore-screenshot-wrap" style="margin-top:10px; border:1px solid #d1d8dd; border-radius:6px; overflow:hidden; display:none;">
                <img id="gicore-screenshot-img" src="" style="width:100%; display:block;">
            </div>
            <a id="gicore-remove-shot" style="font-size:12px; color:#D50000; cursor:pointer; display:none; margin-top:4px;">Remove screenshot</a>

            <label style="font-size:12px; font-weight:600; color:#555; margin-top:16px; display:block;">Attachments (optional)</label>
            <input id="gicore-attachments-input" type="file" multiple style="width:100%; margin-top:6px; font-size:12px;">
            <div id="gicore-attachments-list" style="margin-top:8px; font-size:12px; color:#333;"></div>

            <div style="margin-top:16px; font-size:11px; color:#999;">
                Page: ${window.location.href}<br>
                ${cur_frm ? `Document: ${cur_frm.doc.doctype} — ${cur_frm.doc.name}` : ''}
            </div>
        </div>
        <div style="padding: 14px 20px; border-top:1px solid #eee;">
            <button id="gicore-submit-btn" style="width:100%; background:#D50000; color:#fff; border:none; padding:10px; border-radius:6px; font-size:13px; font-weight:600; cursor:pointer; display:flex; align-items:center; justify-content:center; gap:8px;">
                Submit Issue
            </button>
        </div>
    `;

    document.body.appendChild(overlay);
    document.body.appendChild(drawer);
    requestAnimationFrame(() => {
        overlay.style.opacity = '1';
        drawer.style.transform = 'translateX(0)';
    });

    drawer.querySelector('#gicore-issue-close').onclick = gicore.issue.close;
    drawer.querySelector('#gicore-screenshot-btn').onclick = gicore.issue.capture_screenshot;
    drawer.querySelector('#gicore-remove-shot').onclick = () => {
        gicore.issue._screenshot = null;
        gicore.issue._update_screenshot_preview(null);
    };
    drawer.querySelector('#gicore-attachments-input').onchange = (e) => {
        Array.from(e.target.files).forEach(file => {
            gicore.issue._attachments.push({ file, name: file.name });
        });
        e.target.value = ''; // allow re-selecting same file if removed
        gicore.issue._render_attachments_list();
    };
    drawer.querySelector('#gicore-submit-btn').onclick = gicore.issue.submit;

    document.addEventListener('keydown', gicore.issue._esc_handler = (e) => {
        if (e.key === 'Escape') gicore.issue.close();
    });
};

gicore.issue.close = function (skip_transition) {
    const overlay = document.getElementById('gicore-issue-overlay');
    const drawer = document.getElementById('gicore-issue-drawer');
    document.removeEventListener('keydown', gicore.issue._esc_handler);
    if (!overlay || !drawer) return;
    if (skip_transition) {
        overlay.remove(); drawer.remove();
        return;
    }
    overlay.style.opacity = '0';
    drawer.style.transform = 'translateX(100%)';
    setTimeout(() => { overlay.remove(); drawer.remove(); }, 300);
};

gicore.issue.submit = async function () {
    const subject = document.getElementById('gicore-subject').value.trim();
    const description = document.getElementById('gicore-description').value.trim();
    const priority = document.getElementById('gicore-priority').value;
    const btn = document.getElementById('gicore-submit-btn');
    const issue_type = document.getElementById('gicore-issue-type')?.value || null;

    if (!subject || !description) {
        frappe.show_alert({ message: 'Subject and description are required', indicator: 'orange' }, 4);
        return;
    }

    btn.disabled = true;
    btn.style.opacity = '0.7';

    try {
        let file_urls = [];

        if (gicore.issue._screenshot) {
            btn.innerHTML = `<span class="gicore-spin"></span> Uploading screenshot...`;
            const screenshot_url = await gicore.issue._upload_screenshot(gicore.issue._screenshot);
            if (screenshot_url) file_urls.push(screenshot_url);
        }

        if (gicore.issue._attachments.length) {
            btn.innerHTML = `<span class="gicore-spin"></span> Uploading attachments...`;
            for (const a of gicore.issue._attachments) {
                const url = await gicore.issue._upload_generic_file(a.file);
                if (url) file_urls.push(url);
            }
        }

        btn.innerHTML = `<span class="gicore-spin"></span> Creating issue...`;

        const r = await frappe.call({
            method: 'gicore.gi_support.api.report_issue.create_issue',
            args: {
                subject, description, priority,
                file_urls: JSON.stringify(file_urls),
                route: window.location.href,
                reference_doctype: cur_frm ? cur_frm.doc.doctype : null,
                reference_name: cur_frm ? cur_frm.doc.name : null,
                issue_type: issue_type
            }
        });

        if (r.message) {
            btn.innerHTML = `✓ Submitted`;
            frappe.show_alert({ message: `Issue ${r.message} submitted. Thank you!`, indicator: 'green' }, 5);
            setTimeout(() => gicore.issue.close(), 600);
        }
    } catch (e) {
        btn.disabled = false;
        btn.style.opacity = '1';
        btn.innerHTML = 'Submit Issue';
        frappe.show_alert({ message: 'Failed to submit. Please try again.', indicator: 'red' }, 5);
    }
};

// Uploads a data URL (used for the screenshot) without attaching to any doc yet
gicore.issue._upload_screenshot = function (data_url) {
    return new Promise((resolve, reject) => {
        fetch(data_url)
            .then(res => res.blob())
            .then(blob => {
                const form_data = new FormData();
                form_data.append('file', blob, `issue-screenshot-${Date.now()}.png`);
                form_data.append('is_private', 1);
                // No doctype/docname here — the Issue doesn't exist yet.
                // The backend links this file to the Issue after it's created.

                fetch('/api/method/upload_file', {
                    method: 'POST',
                    headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token },
                    body: form_data
                })
                .then(res => res.json())
                .then(data => resolve(data.message ? data.message.file_url : null))
                .catch(reject);
            })
            .catch(reject);
    });
};

// Uploads a regular File object (from the attachments input), same unattached approach
gicore.issue._upload_generic_file = function (file) {
    return new Promise((resolve, reject) => {
        const form_data = new FormData();
        form_data.append('file', file, file.name);
        form_data.append('is_private', 1);

        fetch('/api/method/upload_file', {
            method: 'POST',
            headers: { 'X-Frappe-CSRF-Token': frappe.csrf_token },
            body: form_data
        })
        .then(res => res.json())
        .then(data => resolve(data.message ? data.message.file_url : null))
        .catch(reject);
    });
};

if (!document.getElementById('gicore-issue-style')) {
    const style = document.createElement('style');
    style.id = 'gicore-issue-style';
    style.innerHTML = `
        .gicore-spin {
            width: 13px; height: 13px; border: 2px solid rgba(255,255,255,0.4);
            border-top-color: #fff; border-radius: 50%;
            display: inline-block; animation: gicore-spin-anim 0.6s linear infinite;
        }
        @keyframes gicore-spin-anim { to { transform: rotate(360deg); } }
    `;
    document.head.appendChild(style);
}

frappe.after_ajax(() => {
    if (document.getElementById('report-issue-fab')) return;
    gicore.issue.render_fab();
});