# Copyright (c) 2026, HM and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import cint, flt, formatdate, getdate, nowdate, add_months

ACTIVE_STATUSES = ["Submitted", "Partially Depreciated", "Fully Depreciated"]
INACTIVE_STATUSES = ["Scrapped", "Sold"]


def execute(filters=None):
	filters = frappe._dict(filters or {})

	if not filters.get("company"):
		frappe.throw(_("Please select a Company"))

	filters.setdefault("as_on_date", nowdate())
	filters.setdefault("show_forecast", 1)
	filters.setdefault("forecast_period_type", "Monthly")
	filters.setdefault("forecast_periods", 12)
	filters.setdefault("forecast_value", "Depreciation Amount")

	forecast_buckets = []
	if cint(filters.show_forecast):
		forecast_buckets = get_forecast_buckets(
			getdate(filters.as_on_date),
			filters.forecast_period_type,
			cint(filters.forecast_periods) or 12,
		)

	columns = get_columns(forecast_buckets)
	data, totals = get_data(filters, forecast_buckets)
	chart = get_chart(forecast_buckets, totals)
	report_summary = get_report_summary(totals, filters)

	return columns, data, None, chart, report_summary


# ---------------------------------------------------------------------------
# Columns
# ---------------------------------------------------------------------------

def get_columns(forecast_buckets):
	columns = [
		{"label": _("Asset"), "fieldname": "asset", "fieldtype": "Link", "options": "Asset", "width": 110},
		{"label": _("Asset Name"), "fieldname": "asset_name", "fieldtype": "Data", "width": 160},
		{"label": _("Category"), "fieldname": "asset_category", "fieldtype": "Link", "options": "Asset Category", "width": 120},
		{"label": _("Status"), "fieldname": "status", "fieldtype": "Data", "width": 110},
		{"label": _("Location"), "fieldname": "location", "fieldtype": "Link", "options": "Location", "width": 100},
		{"label": _("Cost Center"), "fieldname": "cost_center", "fieldtype": "Link", "options": "Cost Center", "width": 130},
		{"label": _("Department"), "fieldname": "department", "fieldtype": "Link", "options": "Department", "width": 110},
		{"label": _("Custodian"), "fieldname": "custodian_name", "fieldtype": "Data", "width": 120},
		{"label": _("Purchase Date"), "fieldname": "purchase_date", "fieldtype": "Date", "width": 95},
		{"label": _("Available For Use"), "fieldname": "available_for_use_date", "fieldtype": "Date", "width": 110},
		{"label": _("Gross Purchase Amount"), "fieldname": "gross_purchase_amount", "fieldtype": "Currency", "options": "currency", "width": 150},
		{"label": _("Opening Accum. Dep."), "fieldname": "opening_accumulated_depreciation", "fieldtype": "Currency", "options": "currency", "width": 140},
		{"label": _("Accum. Dep. (As On Date)"), "fieldname": "accumulated_depreciation", "fieldtype": "Currency", "options": "currency", "width": 160},
		{"label": _("Net Book Value"), "fieldname": "net_book_value", "fieldtype": "Currency", "options": "currency", "width": 130},
		{"label": _("Depreciation Method"), "fieldname": "depreciation_method", "fieldtype": "Data", "width": 130},
		{"label": _("Frequency (Months)"), "fieldname": "frequency_of_depreciation", "fieldtype": "Int", "width": 100},
		{"label": _("Remaining Life (Months)"), "fieldname": "remaining_life_months", "fieldtype": "Int", "width": 120},
		{"label": _("Next Dep. Date"), "fieldname": "next_depreciation_date", "fieldtype": "Date", "width": 100},
		{"label": _("Next Dep. Amount"), "fieldname": "next_depreciation_amount", "fieldtype": "Currency", "options": "currency", "width": 120},
	]

	for bucket in forecast_buckets:
		columns.append({
			"label": bucket["label"],
			"fieldname": bucket["fieldname"],
			"fieldtype": "Currency",
			"options": "currency",
			"width": 110,
		})

	if forecast_buckets:
		columns.append({
			"label": _("Total Forecast"),
			"fieldname": "total_forecast",
			"fieldtype": "Currency",
			"options": "currency",
			"width": 130,
		})

	return columns


# ---------------------------------------------------------------------------
# Forecast bucket helpers
# ---------------------------------------------------------------------------

def get_forecast_buckets(as_on_date, period_type, periods):
	"""Builds calendar buckets (start, end] after as_on_date so assets on
	different depreciation frequencies (monthly/quarterly/yearly) can be
	compared side by side."""
	buckets = []
	start = as_on_date

	for i in range(1, periods + 1):
		if period_type == "Quarterly":
			end = add_months(as_on_date, i * 3)
			quarter = ((getdate(end).month - 1) // 3) + 1
			label = "Q{0} {1}".format(quarter, getdate(end).year)
		elif period_type == "Yearly":
			end = add_months(as_on_date, i * 12)
			label = str(getdate(end).year)
		else:  # Monthly
			end = add_months(as_on_date, i)
			label = formatdate(end, "MMM yyyy")

		buckets.append({
			"idx": i,
			"fieldname": "fcst_{0}".format(i),
			"label": label,
			"start": getdate(start),
			"end": getdate(end),
		})
		start = end

	return buckets


def get_remaining_life_months(future_rows, as_on_date):
	if not future_rows:
		return 0
	last_date = getdate(future_rows[-1].schedule_date)
	months = (last_date.year - as_on_date.year) * 12 + (last_date.month - as_on_date.month)
	return max(months, 0)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

def get_data(filters, forecast_buckets):
	assets = get_assets(filters)
	if not assets:
		return [], {}

	asset_names = [a.name for a in assets]
	finance_book = filters.get("finance_book")

	fb_map = get_finance_book_map(asset_names, finance_book)
	schedule_map = get_schedule_data(asset_names, finance_book)

	as_on_date = getdate(filters.as_on_date)
	currency = frappe.get_cached_value("Company", filters.company, "default_currency")

	data = []
	totals = {
		"gross": 0.0,
		"accum": 0.0,
		"nbv": 0.0,
		"forecast_totals": [0.0] * len(forecast_buckets),
	}

	for asset in assets:
		rows = sorted(schedule_map.get(asset.name, []), key=lambda r: getdate(r.schedule_date))

		accumulated = flt(asset.opening_accumulated_depreciation)
		future_rows = []
		next_dep_date = None
		next_dep_amount = 0.0

		for r in rows:
			r_date = getdate(r.schedule_date)
			if r_date <= as_on_date:
				accumulated += flt(r.depreciation_amount)
			else:
				future_rows.append(r)

		if future_rows:
			next_dep_date = getdate(future_rows[0].schedule_date)
			next_dep_amount = flt(future_rows[0].depreciation_amount)

		gross = flt(asset.gross_purchase_amount)
		nbv = gross - accumulated

		fb = fb_map.get(asset.name)

		row = {
			"asset": asset.name,
			"asset_name": asset.asset_name,
			"asset_category": asset.asset_category,
			"status": asset.status,
			"location": asset.location,
			"cost_center": asset.cost_center,
			"department": asset.department,
			"custodian_name": asset.custodian_name or asset.custodian,
			"purchase_date": asset.purchase_date,
			"available_for_use_date": asset.available_for_use_date,
			"gross_purchase_amount": gross,
			"opening_accumulated_depreciation": flt(asset.opening_accumulated_depreciation),
			"accumulated_depreciation": accumulated,
			"net_book_value": nbv,
			"depreciation_method": fb.depreciation_method if fb else None,
			"frequency_of_depreciation": cint(fb.frequency_of_depreciation) if fb else 0,
			"remaining_life_months": get_remaining_life_months(future_rows, as_on_date),
			"next_depreciation_date": next_dep_date,
			"next_depreciation_amount": next_dep_amount,
			"currency": currency,
		}

		total_forecast = 0.0
		running_nbv = nbv
		for idx, bucket in enumerate(forecast_buckets):
			bucket_dep = sum(
				flt(r.depreciation_amount)
				for r in future_rows
				if bucket["start"] < getdate(r.schedule_date) <= bucket["end"]
			)
			if filters.forecast_value == "Net Book Value":
				running_nbv -= bucket_dep
				row[bucket["fieldname"]] = running_nbv
			else:
				row[bucket["fieldname"]] = bucket_dep

			total_forecast += bucket_dep
			totals["forecast_totals"][idx] += bucket_dep

		if forecast_buckets:
			row["total_forecast"] = total_forecast

		totals["gross"] += gross
		totals["accum"] += accumulated
		totals["nbv"] += nbv

		data.append(row)

	return data, totals


def get_assets(filters):
	conditions = ["a.docstatus = 1", "a.company = %(company)s"]
	values = {"company": filters.company}

	conditions.append("a.purchase_date <= %(as_on_date)s")
	values["as_on_date"] = filters.as_on_date

	simple_filters = {
		"asset_category": "a.asset_category",
		"location": "a.location",
		"cost_center": "a.cost_center",
		"department": "a.department",
		"custodian": "a.custodian",
		"asset": "a.name",
	}
	for key, column in simple_filters.items():
		if filters.get(key):
			conditions.append("{0} = %({1})s".format(column, key))
			values[key] = filters.get(key)

	status_list = list(ACTIVE_STATUSES)
	if cint(filters.get("include_scrapped_sold")):
		status_list += INACTIVE_STATUSES
	conditions.append("a.status in %(status_list)s")
	values["status_list"] = status_list

	condition_str = " and ".join(conditions)

	return frappe.db.sql(
		"""
		select
			a.name, a.asset_name, a.asset_category, a.status, a.location,
			a.cost_center, a.department, a.custodian,
			e.employee_name as custodian_name,
			a.purchase_date, a.available_for_use_date,
			a.gross_purchase_amount, a.opening_accumulated_depreciation
		from `tabAsset` a
		left join `tabEmployee` e on e.name = a.custodian
		where {condition_str}
		order by a.asset_category, a.name
		""".format(condition_str=condition_str),
		values,
		as_dict=True,
	)


def get_finance_book_map(asset_names, finance_book=None):
	"""One Asset Finance Book row per asset (filtered/first) -> depreciation
	method, frequency etc. Works the same across ERPNext versions."""
	filters = {"parent": ["in", asset_names], "parenttype": "Asset"}
	if finance_book:
		filters["finance_book"] = finance_book

	rows = frappe.get_all(
		"Asset Finance Book",
		filters=filters,
		fields=["parent", "finance_book", "depreciation_method", "frequency_of_depreciation", "total_number_of_depreciations"],
		order_by="parent, idx",
	)

	result = {}
	for r in rows:
		result.setdefault(r.parent, r)
	return result


def get_schedule_data(asset_names, finance_book=None):
	"""Returns {asset_name: [schedule_rows]}. Handles both the newer
	standalone 'Asset Depreciation Schedule' doctype (v14+) and the older
	model where 'Depreciation Schedule' rows sit directly on the Asset."""
	result = {}

	if frappe.db.exists("DocType", "Asset Depreciation Schedule"):
		ads_filters = {"asset": ["in", asset_names], "docstatus": ["!=", 2]}
		if finance_book:
			ads_filters["finance_book"] = finance_book

		ads_rows = frappe.get_all(
			"Asset Depreciation Schedule",
			filters=ads_filters,
			fields=["name", "asset"],
			order_by="asset, creation desc",
		)

		ads_map = {}
		for r in ads_rows:
			ads_map.setdefault(r.asset, r.name)  # most recent per asset

		if not ads_map:
			return result

		name_to_asset = {v: k for k, v in ads_map.items()}
		rows = frappe.get_all(
			"Depreciation Schedule",
			filters={"parent": ["in", list(ads_map.values())]},
			fields=["parent", "schedule_date", "depreciation_amount"],
			order_by="parent, schedule_date",
		)
		for r in rows:
			asset = name_to_asset.get(r.parent)
			if asset:
				result.setdefault(asset, []).append(r)
	else:
		row_filters = {"parenttype": "Asset", "parent": ["in", asset_names]}
		if finance_book:
			row_filters["finance_book"] = finance_book

		rows = frappe.get_all(
			"Depreciation Schedule",
			filters=row_filters,
			fields=["parent as asset", "schedule_date", "depreciation_amount"],
			order_by="parent, schedule_date",
		)
		for r in rows:
			result.setdefault(r.asset, []).append(r)

	return result


# ---------------------------------------------------------------------------
# Chart / summary
# ---------------------------------------------------------------------------

def get_chart(forecast_buckets, totals):
	if not forecast_buckets or not totals:
		return None

	return {
		"data": {
			"labels": [b["label"] for b in forecast_buckets],
			"datasets": [
				{"name": _("Forecasted Depreciation"), "values": totals.get("forecast_totals", [])}
			],
		},
		"type": "bar",
		"colors": ["#D50000"],
	}


def get_report_summary(totals, filters):
	if not totals:
		return []

	currency = frappe.get_cached_value("Company", filters.company, "default_currency")

	summary = [
		{"label": _("Total Gross Value"), "value": totals.get("gross", 0), "datatype": "Currency", "currency": currency},
		{"label": _("Total Accum. Depreciation"), "value": totals.get("accum", 0), "datatype": "Currency", "currency": currency, "indicator": "Red"},
		{"label": _("Total Net Book Value"), "value": totals.get("nbv", 0), "datatype": "Currency", "currency": currency, "indicator": "Green"},
	]

	if totals.get("forecast_totals"):
		summary.append({
			"label": _("Total Forecasted Depreciation"),
			"value": sum(totals["forecast_totals"]),
			"datatype": "Currency",
			"currency": currency,
			"indicator": "Orange",
		})

	return summary
