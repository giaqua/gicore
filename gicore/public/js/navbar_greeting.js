// navbar_greeting.js
// Shows a time-based greeting + user name + date in the Frappe/ERPNext navbar.

(function () {
	const T = {
		en: {
			morning: "Good Morning",
			afternoon: "Good Afternoon",
			evening: "Good Evening",
			night: "Good Night",
		},
		ar: {
			morning: "صباح الخير",
			afternoon: "مساء الخير",
			evening: "مساء الخير",
			night: "طاب مساؤك",
		},
	};

	const ICONS = {
		// sun
		morning:
			'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>',
		// bright sun (afternoon)
		afternoon:
			'<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.2 4.2l1.4 1.4M18.4 18.4l1.4 1.4M1 12h2M21 12h2M4.2 19.8l1.4-1.4M18.4 5.6l1.4-1.4" fill="none"/></svg>',
		// sunset
		evening:
			'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 18a5 5 0 0 0-10 0M12 9V2M4.2 10.2l1.4 1.4M1 18h2M21 18h2M18.4 11.6l1.4-1.4M23 22H1M16 5l-4 4-4-4"/></svg>',
		// moon
		night:
			'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"/></svg>',
	};

	function period(hour) {
		if (hour >= 5 && hour < 12) return "morning";
		if (hour >= 12 && hour < 17) return "afternoon";
		if (hour >= 17 && hour < 21) return "evening";
		return "night";
	}

	function render() {
		const lang = (frappe.boot && frappe.boot.lang) === "ar" ? "ar" : "en";
		const now = new Date();
		const p = period(now.getHours());
		const name =
			frappe.session.user_fullname ||
			(frappe.boot.user && frappe.boot.user.first_name) ||
			frappe.session.user;

		const dateStr = now.toLocaleDateString(lang === "ar" ? "ar-SA" : "en-GB", {
			weekday: "long",
			day: "numeric",
			month: "short",
			year: "numeric",
		});

		const $el = $("#hm-navbar-greeting");
		if (!$el.length) return;

		$el.attr("data-period", p);
		$el.find(".hm-greet-icon").html(ICONS[p]);
		$el.find(".hm-greet-text").text(T[lang][p]);
		$el.find(".hm-greet-name").text(name);
		$el.find(".hm-greet-date").text(dateStr);
	}

	function mount() {
		if ($("#hm-navbar-greeting").length) return true;

		const $brand = $(".navbar .navbar-brand").first();
		if (!$brand.length) return false;

		const $el = $(`
			<div id="hm-navbar-greeting" class="hm-navbar-greeting">
				<span class="hm-greet-icon"></span>
				<div class="hm-greet-body">
					<span class="hm-greet-text"></span>
					<span class="hm-greet-name"></span>
				</div>
				<span class="hm-greet-divider"></span>
				<span class="hm-greet-date"></span>
			</div>
		`);
		$brand.after($el);
		return true;
	}

	function init() {
		let tries = 0;
		const wait = setInterval(() => {
			if (mount() || ++tries > 40) {
				clearInterval(wait);
				render();
				// refresh every minute so the greeting changes at 12:00, 17:00 ...
				setInterval(render, 60 * 1000);
			}
		}, 250);
	}

	$(document).ready(init);
})();