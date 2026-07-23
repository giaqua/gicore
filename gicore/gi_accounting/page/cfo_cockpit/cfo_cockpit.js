frappe.pages['cfo-cockpit'].on_page_load = function (wrapper) {
	new gicore.CFOCockpit(wrapper);
};

frappe.provide('gicore');

gicore.CFOCockpit = class CFOCockpit {
	constructor(wrapper) {
		this.wrapper = wrapper;
		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __('CFO Cockpit'),
			single_column: true,
		});
		this.setup_filters();
		this.setup_layout();
		this.reload();
	}

	setup_filters() {
		this.company = frappe.defaults.get_default('company');

		this.company_field = this.page.add_field({
			label: __('Company'),
			fieldtype: 'Link',
			fieldname: 'company',
			options: 'Company',
			default: this.company,
			reqd: 1,
			change: () => {
				const val = this.company_field.get_value();
				if (val && val !== this.company) {
					this.company = val;
					this.reload();
				}
			},
		});

		this.weeks_field = this.page.add_field({
			label: __('Forecast Weeks'),
			fieldtype: 'Select',
			fieldname: 'weeks',
			options: '4\n8\n12',
			default: '8',
			change: () => this.reload(),
		});

		this.page.set_primary_action(__('Refresh'), () => this.reload(), 'refresh');
	}

	setup_layout() {
		this.$container = $(`
			<div class="cfo-cockpit">
				<div class="cfo-kpis row"></div>

				<div class="cfo-section">
					<h5>${__('Cash & Bank Position')}</h5>
					<div class="row">
						<div class="col-sm-7"><div class="cfo-cash-table"></div></div>
						<div class="col-sm-5"><div class="cfo-cash-chart"></div></div>
					</div>
				</div>

				<div class="cfo-section">
					<h5>${__('Receivables Aging')}</h5>
					<div class="row">
						<div class="col-sm-6"><div class="cfo-ar-chart"></div></div>
						<div class="col-sm-6"><div class="cfo-ar-top"></div></div>
					</div>
				</div>

				<div class="cfo-section">
					<h5>${__('Payables Aging')}</h5>
					<div class="row">
						<div class="col-sm-6"><div class="cfo-ap-chart"></div></div>
						<div class="col-sm-6"><div class="cfo-ap-top"></div></div>
					</div>
				</div>

				<div class="cfo-section">
					<h5>${__('Cash Flow Forecast')}</h5>
					<p class="text-muted small">${__('Projected from open AR/AP due dates. Assumes on-time settlement — a directional view, not a guarantee.')}</p>
					<div class="cfo-forecast-chart"></div>
				</div>
			</div>
		`).appendTo(this.page.main);
	}

	reload() {
		if (!this.company) return;

		frappe.dom.freeze(__('Loading CFO Cockpit...'));
		frappe.call({
			method: 'gicore.gi_accounting.page.cfo_cockpit.cfo_cockpit.get_cockpit_data',
			args: {
				company: this.company,
				weeks: this.weeks_field.get_value() || 8,
			},
			callback: (r) => {
				frappe.dom.unfreeze();
				if (r.message) {
					this.data = r.message;
					this.render_all();
				}
			},
			error: () => frappe.dom.unfreeze(),
		});
	}

	fmt(n) {
		return format_currency(n, frappe.boot.sysdefaults.currency);
	}

	render_all() {
		this.render_kpis();
		this.render_cash_bank();
		this.render_aging('ar');
		this.render_aging('ap');
		this.render_forecast();
	}

	render_kpis() {
		const d = this.data;
		const cash = d.cash_bank.total;
		const ar = d.ar.total;
		const ap = d.ap.total;
		const net = cash + ar - ap;

		const cards = [
			{ label: __('Cash & Bank'), value: cash, color: '#010BCE' },
			{ label: __('Receivables (AR)'), value: ar, color: '#2e7d32' },
			{ label: __('Payables (AP)'), value: ap, color: '#D50000' },
			{ label: __('Net Position'), value: net, color: net >= 0 ? '#2e7d32' : '#D50000' },
		];

		const $kpis = this.$container.find('.cfo-kpis').empty();
		cards.forEach((c) => {
			$kpis.append(`
				<div class="col-sm-3">
					<div class="cfo-kpi-card" style="border-top:3px solid ${c.color}">
						<div class="cfo-kpi-label">${c.label}</div>
						<div class="cfo-kpi-value" style="color:${c.color}">${this.fmt(c.value)}</div>
					</div>
				</div>
			`);
		});
	}

	render_cash_bank() {
		const rows = this.data.cash_bank.accounts;
		const $table = this.$container.find('.cfo-cash-table').empty();

		let html = `<table class="table table-bordered"><thead><tr>
			<th>${__('Account')}</th><th class="text-right">${__('Balance')}</th>
		</tr></thead><tbody>`;
		rows.forEach((r) => {
			html += `<tr><td>${frappe.utils.escape_html(r.account)}</td><td class="text-right">${this.fmt(r.balance)}</td></tr>`;
		});
		html += `</tbody></table>`;
		$table.html(rows.length ? html : `<p class="text-muted">${__('No bank/cash accounts found')}</p>`);

		const $chart = this.$container.find('.cfo-cash-chart').empty();
		if (rows.length) {
			new frappe.Chart($chart[0], {
				data: {
					labels: rows.map((r) => r.account),
					datasets: [{ values: rows.map((r) => r.balance) }],
				},
				type: 'bar',
				height: 220,
				colors: ['#010BCE'],
			});
		}
	}

	render_aging(type) {
		const d = this.data[type];
		const labels = [__('Not Due'), __('1-30'), __('31-60'), __('61-90'), __('90+')];
		const keys = ['not_due', '1_30', '31_60', '61_90', '90_plus'];
		const values = keys.map((k) => d.buckets[k]);

		const $chart = this.$container.find(`.cfo-${type}-chart`).empty();
		new frappe.Chart($chart[0], {
			data: { labels, datasets: [{ values }] },
			type: 'bar',
			height: 220,
			colors: [type === 'ar' ? '#2e7d32' : '#D50000'],
		});

		const $top = this.$container.find(`.cfo-${type}-top`).empty();
		const party_label = type === 'ar' ? __('Customer') : __('Supplier');
		let html = `<table class="table table-bordered"><thead><tr>
			<th>${party_label}</th><th class="text-right">${__('Overdue')}</th>
		</tr></thead><tbody>`;
		d.top_overdue.forEach((r) => {
			html += `<tr><td>${frappe.utils.escape_html(r.party || '')}</td><td class="text-right">${this.fmt(r.overdue)}</td></tr>`;
		});
		html += `</tbody></table>`;
		$top.html(d.top_overdue.length ? html : `<p class="text-muted">${__('No overdue items')}</p>`);
	}

	render_forecast() {
		const weeks = this.data.forecast.weeks;
		const $chart = this.$container.find('.cfo-forecast-chart').empty();

		new frappe.Chart($chart[0], {
			data: {
				labels: weeks.map((w) => w.week_start),
				datasets: [
					{ name: __('Inflow'), values: weeks.map((w) => w.inflow), chartType: 'bar' },
					{ name: __('Outflow'), values: weeks.map((w) => -w.outflow), chartType: 'bar' },
					{
						name: __('Projected Balance'),
						values: weeks.map((w) => w.projected_balance),
						chartType: 'line',
					},
				],
			},
			type: 'axis-mixed',
			height: 280,
			colors: ['#2e7d32', '#D50000', '#010BCE'],
			axisOptions: { xIsSeries: true },
		});
	}
};