// Copyright (c) 2026, GI Aqua Tech and contributors
// For license information, please see license.txt

// frappe.ui.form.on("HM Business Card", {
//     refresh(frm) {
//         frm.add_custom_button(__("Print Card"), function() {
//             frappe.call({
//                 method: "gicore.gi_hr.doctype.hm_business_card.hm_business_card.get_business_card_pdf",
//                 args: { docname: frm.doc.name },
//                 callback: function(r) {
//                     if (r.message) {
//                         const byteChars = atob(r.message);
//                         const byteNumbers = new Array(byteChars.length);
//                         for (let i = 0; i < byteChars.length; i++) {
//                             byteNumbers[i] = byteChars.charCodeAt(i);
//                         }
//                         const blob = new Blob([new Uint8Array(byteNumbers)], { type: "application/pdf" });
//                         window.open(URL.createObjectURL(blob));
//                     }
//                 }
//             });
//         });
//     }
// });

frappe.ui.form.on("HM Business Card", {
    refresh(frm) {
        frm.add_custom_button(__("Print Card"), function() {
            frappe.call({
                method: "gicore.gi_hr.doctype.hm_business_card.hm_business_card.get_business_card_html",
                args: { docname: frm.doc.name },
                callback: function(r) {
                    if (!r.message) return;

                    const dialog = new frappe.ui.Dialog({
                        title: __("Review Business Card"),
                        size: "small",
                        fields: [
                            { fieldtype: "HTML", fieldname: "preview" }
                        ],
                        primary_action_label: __("Print"),
                        primary_action() {
                            const iframe = dialog.$wrapper.find("iframe")[0];
                            iframe.contentWindow.focus();
                            iframe.contentWindow.print();
                        }
                    });

                    dialog.fields_dict.preview.$wrapper.html(`
                        <div style="display:flex; justify-content:center; padding:16px; background:#eef1f2;">
                            <iframe id="card-preview-frame"
                                style="width:85mm; height:55mm; border:1px solid #d1d8dd; border-radius:4px; box-shadow:0 4px 16px rgba(0,0,0,0.15);"
                                srcdoc="${r.message.replace(/"/g, "&quot;")}">
                            </iframe>
                        </div>
                    `);

                    dialog.show();
                }
            });
        });
    }
});