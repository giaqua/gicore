import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import flt, getdate

# --- Adjust these to match your Daily Operation Report doctype ---
DOR_DOCTYPE = "Daily Operation Report"
DOR_DATE_FIELD = "date"
DOR_PROJECT_FIELD = "project"
DOR_TREATED_WATER_FIELD = "waste_water_treated_volume"


class ProjectOverheadAllocation(Document):
	def validate(self):
		self.validate_dates()
		self.set_total_cost()
		self.allocate_cost()

	@frappe.whitelist()
	def fetch_and_allocate(self):
		self.validate_dates()
		self.fetch_child_accounts()
		self.set_total_cost()
		self.fetch_treated_water()
		self.allocate_cost()

	# ------------------------------------------------------------------
	def validate_dates(self):
		if not (self.from_date and self.to_date):
			frappe.throw(_("From Date and To Date are mandatory"))
		if getdate(self.from_date) > getdate(self.to_date):
			frappe.throw(_("From Date cannot be after To Date"))

	# ------------------------------------------------------------------
	def fetch_child_accounts(self):
		parents = list({d.account for d in self.parent_accounts if d.account})
		if not parents:
			frappe.throw(_("Please add at least one Parent Account"))

		# All ledger (is_group = 0) accounts under the selected parents
		ledger_accounts = [
			r[0]
			for r in frappe.db.sql(
				"""
				SELECT DISTINCT child.name
				FROM `tabAccount` child
				INNER JOIN `tabAccount` parent
					ON child.lft >= parent.lft
					AND child.rgt <= parent.rgt
					AND child.company = parent.company
				WHERE parent.name IN %(parents)s
					AND child.is_group = 0
				ORDER BY child.lft
				""",
				{"parents": parents},
			)
		]

		self.set("child_accounts", [])
		if not ledger_accounts:
			frappe.msgprint(_("No ledger accounts found under the selected Parent Accounts"))
			return

		# Net expense (debit - credit) per account within the period
		balances = dict(
			frappe.db.sql(
				"""
				SELECT account, SUM(debit - credit)
				FROM `tabGL Entry`
				WHERE account IN %(accounts)s
					AND posting_date BETWEEN %(from_date)s AND %(to_date)s
					AND is_cancelled = 0
					AND voucher_type != 'Period Closing Voucher'
				GROUP BY account
				""",
				{
					"accounts": ledger_accounts,
					"from_date": self.from_date,
					"to_date": self.to_date,
				},
			)
		)

		precision = self.precision("amount", "child_accounts")
		for account in ledger_accounts:
			amount = flt(balances.get(account), precision)
			if amount:
				self.append("child_accounts", {"account": account, "amount": amount})

	# ------------------------------------------------------------------
	def set_total_cost(self):
		self.total_cost = flt(
			sum(flt(d.amount) for d in self.child_accounts),
			self.precision("total_cost"),
		)* self.allocation_percentage / 100

	# ------------------------------------------------------------------
	def fetch_treated_water(self):
		rows = frappe.db.sql(
			f"""
			SELECT
				`{DOR_PROJECT_FIELD}` AS project,
				SUM(`{DOR_TREATED_WATER_FIELD}`) AS treated_water
			FROM `tab{DOR_DOCTYPE}`
			WHERE docstatus = 1
				AND `{DOR_DATE_FIELD}` BETWEEN %(from_date)s AND %(to_date)s
				AND IFNULL(`{DOR_PROJECT_FIELD}`, '') != ''
			GROUP BY `{DOR_PROJECT_FIELD}`
			HAVING SUM(`{DOR_TREATED_WATER_FIELD}`) > 0
			ORDER BY `{DOR_PROJECT_FIELD}`
			""",
			{"from_date": self.from_date, "to_date": self.to_date},
			as_dict=True,
		)

		self.set("project_treated_water", [])
		for r in rows:
			self.append(
				"project_treated_water",
				{"project": r.project, "treated_water": flt(r.treated_water)},
			)

		if not rows:
			frappe.msgprint(_("No Daily Operation Reports found in this period"))

	# ------------------------------------------------------------------
	def allocate_cost(self):
		rows = self.project_treated_water
		self.total_treated_water = flt(
			sum(flt(d.treated_water) for d in rows),
			self.precision("total_treated_water"),
		)

		precision = self.precision("allocated_amount", "project_treated_water")

		if not self.total_treated_water:
			self.cost_per_m3 = 0
			for d in rows:
				d.allocated_amount = 0
			return

		# keep full precision for the calculation, round only for display
		rate = flt(self.total_cost) / flt(self.total_treated_water)
		self.cost_per_m3 = flt(rate, self.precision("cost_per_m3"))

		allocated = 0
		for i, d in enumerate(rows):
			if i == len(rows) - 1:
				# last row absorbs rounding so the sum equals total_cost exactly
				d.allocated_amount = flt(flt(self.total_cost) - allocated, precision)
			else:
				d.allocated_amount = flt(flt(d.treated_water) * rate, precision)
				allocated += d.allocated_amount


	@frappe.whitelist()
	def distribute_to_dor(self):
		if self.is_new():
			frappe.throw(_("Please save the document first"))

		projects = [d.project for d in self.project_treated_water if d.project]
		if not projects or not flt(self.total_treated_water):
			frappe.throw(_("Nothing to distribute. Run Fetch & Allocate first."))

		reports = frappe.db.sql(
			f"""
			SELECT name, `{DOR_TREATED_WATER_FIELD}` AS volume
			FROM `tab{DOR_DOCTYPE}`
			WHERE docstatus = 1
				AND `{DOR_DATE_FIELD}` BETWEEN %(from_date)s AND %(to_date)s
				AND `{DOR_PROJECT_FIELD}` IN %(projects)s
			ORDER BY `{DOR_DATE_FIELD}`, name
			""",
			{"from_date": self.from_date, "to_date": self.to_date, "projects": projects},
			as_dict=True,
		)

		if not reports:
			frappe.throw(_("No Daily Operation Reports found in this period"))

		# unrounded rate so totals stay exact
		rate = flt(self.total_cost) / flt(self.total_treated_water)
		precision = frappe.get_meta(DOR_DOCTYPE).get_field("overhead_cost").precision or 2
		precision = int(precision)

		distributed = 0
		last_with_volume = max(i for i, r in enumerate(reports) if flt(r.volume)) if any(flt(r.volume) for r in reports) else -1

		for i, r in enumerate(reports):
			if i == last_with_volume:
				# last report absorbs rounding so sum equals total_cost exactly
				cost = flt(flt(self.total_cost) - distributed, precision)
			else:
				cost = flt(flt(r.volume) * rate, precision)
				distributed += cost

			frappe.db.set_value(
				DOR_DOCTYPE,
				r.name,
				{"overhead_cost_per_m3": flt(self.cost_per_m3), "overhead_cost": cost},
				update_modified=False,
			)

		return {"count": len(reports), "total": flt(self.total_cost)}