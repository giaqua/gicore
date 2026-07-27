/**
 * Attachment Preview (Eye Icon) — Frappe Client Script
 * ------------------------------------------------------
 * Adds a preview (eye) icon next to every file in the form's
 * "Attachments" sidebar area. Clicking it opens an inline preview
 * for images, PDF, video, CSV, and Excel (xlsx/xls) without
 * downloading the file.
 *
 * INSTALL:
 * 1. Save this file to your app, e.g.:
 *      your_app/public/js/attachment_preview.js
 * 2. In hooks.py add:
 *      app_include_js = ["/assets/your_app/js/attachment_preview.js"]
 * 3. bench build --app your_app && bench clear-cache
 *
 * NOTE: relies on the current DOM structure of the attachments
 * sidebar (.form-attachments .attachment-row). If a Frappe version
 * upgrade changes those classes, inspect the sidebar HTML and
 * adjust the selectors in add_preview_icons().
 */

frappe.provide("hm_attachment_preview");

const EYE_ICON_SVG = `
<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
     stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
  <circle cx="12" cy="12" r="3"></circle>
</svg>`;

// Re-scan periodically since the sidebar re-renders on refresh, after upload,
// and there's no single reliable event for every Frappe version.
$(document).on("form-refresh form-load", function () {
	setTimeout(() => hm_attachment_preview.add_icons(), 400);
});

frappe.ui.form.on("*", {
	refresh() {
		setTimeout(() => hm_attachment_preview.add_icons(), 600);
	},
});

// Belt-and-suspenders: catch the case where attachments are added/removed
// without a full form refresh (e.g. via the "Attach File" dialog).
setInterval(() => hm_attachment_preview.add_icons(), 2000);

hm_attachment_preview.add_icons = function () {
	// Matches the actual anchor structure found in the sidebar:
	// <a href="/private/files/xyz.pdf" class="ellipsis" title="...">
	const $links = $('a.ellipsis[href*="/files/"]');

	$links.each(function () {
		const $link = $(this);

		// Skip if we already added an icon right before this link
		if ($link.prev(".hm-preview-eye").length) return;

		const file_url = $link.attr("href");
		if (!file_url) return;

		const $icon = $(`<span class="hm-preview-eye" title="Preview"
			style="cursor:pointer;margin-right:6px;display:inline-flex;
			align-items:center;color:var(--text-muted);vertical-align:middle;">${EYE_ICON_SVG}</span>`);

		$icon.on("click", function (e) {
			e.preventDefault();
			e.stopPropagation();
			hm_attachment_preview.show(file_url);
		});

		$link.before($icon);
	});
};

hm_attachment_preview.show = function (file_url) {
	const ext = (file_url.split(".").pop() || "").toLowerCase().split("?")[0];

	const d = new frappe.ui.Dialog({
		title: __("Preview"),
		size: "large",
	});
	d.$wrapper.find(".modal-dialog").css("max-width", "900px");
	d.show();
	d.$body.html(`<div class="text-muted text-center" style="padding:40px;">${__("Loading...")}</div>`);

	const IMAGE_EXT = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"];
	const VIDEO_EXT = ["mp4", "webm", "ogg", "mov"];

	if (IMAGE_EXT.includes(ext)) {
		d.$body.html(`<div style="text-align:center;">
			<img src="${file_url}" style="max-width:100%;max-height:75vh;" />
		</div>`);
	} else if (ext === "pdf") {
		d.$body.html(`<iframe src="${file_url}" style="width:100%;height:75vh;border:none;"></iframe>`);
	} else if (VIDEO_EXT.includes(ext)) {
		d.$body.html(`<video controls style="width:100%;max-height:75vh;">
			<source src="${file_url}">${__("Your browser does not support video playback.")}
		</video>`);
	} else if (ext === "csv") {
		fetch(file_url)
			.then((r) => r.text())
			.then((text) => {
				const rows = text
					.split(/\r?\n/)
					.filter((r) => r.length)
					.map((r) => r.split(","));
				hm_attachment_preview.render_table(d, rows);
			})
			.catch(() => hm_attachment_preview.fallback(d, file_url));
	} else if (["xlsx", "xls"].includes(ext)) {
		if (typeof XLSX === "undefined") {
			d.$body.html(`<div class="text-danger" style="padding:20px;">
				${__("SheetJS (XLSX) library not loaded. Check app_include_js in hooks.py.")}</div>`);
			return;
		}
		fetch(file_url)
			.then((r) => r.arrayBuffer())
			.then((buf) => {
				const wb = XLSX.read(buf, { type: "array" });
				const sheet = wb.Sheets[wb.SheetNames[0]];
				const rows = XLSX.utils.sheet_to_json(sheet, { header: 1, defval: "" });
				hm_attachment_preview.render_table(d, rows, wb.SheetNames);
			})
			.catch((err) => {
				console.error("hm_attachment_preview xlsx error:", err);
				hm_attachment_preview.fallback(d, file_url);
			});
	} else {
		hm_attachment_preview.fallback(d, file_url);
	}
};

hm_attachment_preview.render_table = function (d, rows, sheet_names) {
	if (!rows.length) {
		d.$body.html(`<div class="text-muted">${__("Empty file")}</div>`);
		return;
	}
	let html = `<div style="max-height:70vh;overflow:auto;">`;
	if (sheet_names && sheet_names.length > 1) {
		html += `<div class="text-muted small" style="margin-bottom:6px;">
			${__("Sheet")}: ${sheet_names[0]} (${sheet_names.length} ${__("sheets total")})</div>`;
	}
	html += `<table class="table table-bordered table-sm" style="font-size:12px;">`;
	rows.forEach((row, i) => {
		html += "<tr>";
		row.forEach((cell) => {
			const tag = i === 0 ? "th" : "td";
			html += `<${tag}>${frappe.utils.escape_html(String(cell ?? ""))}</${tag}>`;
		});
		html += "</tr>";
	});
	html += "</table></div>";
	d.$body.html(html);
};

hm_attachment_preview.fallback = function (d, file_url) {
	d.$body.html(`<div class="text-center" style="padding:30px;">
		${__("No inline preview available for this file type.")}<br><br>
		<a class="btn btn-sm btn-default" href="${file_url}" target="_blank">${__("Open file")}</a>
	</div>`);
};