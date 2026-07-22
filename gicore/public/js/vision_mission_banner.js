(function () {
    let vmDataCache = null;
    let buttonInserted = false; // guard flag — set immediately, not after fetch resolves

    function getDefaultCompany() {
        return frappe.defaults.get_default('company');
    }

    function fetchVMData(callback) {
        if (vmDataCache !== null) {
            callback(vmDataCache);
            return;
        }
        const company = getDefaultCompany();
        if (!company) {
            callback(false);
            return;
        }
        frappe.db.get_value('Company', company,
            ['custom_show_vision_mission as show_vision_mission', 'custom_vision_en as vision_en', 'custom_vision_ar as vision_ar', 'custom_mission_en as mission_en', 'custom_mission_ar as mission_ar'],
            (r) => {
                vmDataCache = r;
                callback(r);
            }
        );
    }

    function showVMDialog(data) {
        const d = new frappe.ui.Dialog({
            title: '',
            size: 'large',
            fields: [
                {
                    fieldtype: 'HTML',
                    fieldname: 'vm_content',
                    options: `
                    <div class="gi-vm-wrap">
                        <div class="gi-vm-header">
                            <div class="gi-vm-header-icon">💧</div>
                            <div>
                                <div class="gi-vm-header-title">Vision & Mission</div>
                                <div class="gi-vm-header-title-ar">الرؤية والرسالة</div>
                            </div>
                        </div>
                        <div class="gi-vm-body">
                            <div class="gi-vm-card" dir="ltr">
                                <div class="gi-vm-label gi-vm-label-vision">VISION</div>
                                <p>${frappe.utils.escape_html(data.vision_en || '')}</p>
                                <div class="gi-vm-label gi-vm-label-mission">MISSION</div>
                                <p>${frappe.utils.escape_html(data.mission_en || '')}</p>
                            </div>
                            <div class="gi-vm-divider"></div>
                            <div class="gi-vm-card" dir="rtl">
                                <div class="gi-vm-label gi-vm-label-vision">الرؤية</div>
                                <p>${frappe.utils.escape_html(data.vision_ar || '')}</p>
                                <div class="gi-vm-label gi-vm-label-mission">الرسالة</div>
                                <p>${frappe.utils.escape_html(data.mission_ar || '')}</p>
                            </div>
                        </div>
                    </div>`
                }
            ]
        });
        d.$wrapper.find('.modal-header').hide();
        d.$wrapper.find('.modal-dialog').css('max-width', '760px');
        d.show();
    }

    function addVMButton(navbar) {
        if (buttonInserted) return;      // guard set synchronously — blocks all parallel calls
        if (navbar.querySelector('.gi-vm-btn')) return;

        buttonInserted = true; // lock immediately, before async fetch even starts

        fetchVMData((data) => {
            if (!data || !cint(data.show_vision_mission) || (!data.vision_en && !data.vision_ar)) {
                buttonInserted = false; // nothing to show — release lock so it can retry later if data changes
                return;
            }

            const btn = document.createElement('button');
            btn.className = 'btn btn-default gi-vm-btn gi-vm-btn-icon-only';
            btn.innerHTML = '💧';
            btn.title = 'Vision & Mission / الرؤية والرسالة';
            btn.onclick = () => showVMDialog(data);

            navbar.appendChild(btn);
        });
    }

    const observer = new MutationObserver(() => {
        const navbar = document.querySelector('.navbar .container, .navbar-collapse, .navbar');
        if (navbar) addVMButton(navbar);
    });

    observer.observe(document.documentElement, { childList: true, subtree: true });
})();