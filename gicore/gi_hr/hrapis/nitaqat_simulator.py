"""
Nitaqat Band Simulator
-----------------------
Classifies current Saudization standing into a Nitaqat band and lets
you simulate how a hiring/termination plan would shift that band
*before* you commit to it.

IMPORTANT — thresholds are sector- and size-specific:
Nitaqat thresholds are not a single national number — MHRSD/Qiwa
publishes a matrix of Saudization % cutoffs per economic activity
classification AND establishment size category (very small / small /
medium / large / giant). There is no way to hardcode a universally
correct threshold table here. NITAQAT_BANDS below is a PLACEHOLDER —
log into your Qiwa account, pull the band matrix for your specific
activity + size classification, and replace the values before relying
on this for real decisions.

Also a simplification flag: the official Nitaqat calculation applies
weighting (e.g. part-time employees count fractionally, certain wage
thresholds/gender/disability factors can adjust the count) that goes
beyond a flat Saudi/non-Saudi headcount ratio. This engine uses a
simple headcount ratio by default — confirm against Qiwa's calculator
whether weighting applies to your establishment before treating the
output as authoritative, and extend WEIGHT_RULES below if it does.

Drop into a custom app, e.g.:
  your_app/your_app/nitaqat/simulator.py
"""

import frappe

# ---------------------------------------------------------------------
# CONFIGURATION — replace with your actual Qiwa-published thresholds
# ---------------------------------------------------------------------

# Ordered highest to lowest. First band whose min_percent the
# establishment's Saudization % meets or exceeds is the result.
NITAQAT_BANDS = [
    {"band": "Platinum", "min_percent": 40},      # PLACEHOLDER
    {"band": "High Green", "min_percent": 30},     # PLACEHOLDER
    {"band": "Medium Green", "min_percent": 20},   # PLACEHOLDER
    {"band": "Low Green", "min_percent": 10},      # PLACEHOLDER
    {"band": "Red", "min_percent": 0},
]

# Value(s) in Employee.nationality that count as Saudi. ERPNext's
# default Country list uses "Saudi Arabia" / "Saudi Arabian" depending
# on version — confirm against your actual data, or switch this to a
# custom checkbox field (e.g. "custom_is_saudi") if you have one.
SAUDI_NATIONALITY_VALUES = ["Saudi Arabia", "Saudi Arabian","Saudi, Saudi Arabian"]

# Set True only once you've confirmed weighting applies and have
# implemented the actual factors in apply_weighting() below.
USE_WEIGHTING = False


# ---------------------------------------------------------------------

def _is_saudi(employee_row):
    return employee_row.get("nationality") in SAUDI_NATIONALITY_VALUES


def apply_weighting(saudi_count, non_saudi_count, employees):
    """
    Placeholder hook for Nitaqat's official weighting rules (part-time
    fractional credit, wage-band multipliers, etc.). Currently a
    pass-through — extend this if your activity classification
    requires it.
    """
    return saudi_count, non_saudi_count


def classify_band(saudization_percent):
    for band in NITAQAT_BANDS:
        if saudization_percent >= band["min_percent"]:
            return band["band"]
    return NITAQAT_BANDS[-1]["band"]


@frappe.whitelist()
def get_companies():
    """Real company list, for populating the dashboard's selector."""
    return frappe.get_all("Company", pluck="name")


@frappe.whitelist()
def get_snapshot(company):

    """Current live Saudization % and Nitaqat band for `company`."""
    employees = frappe.get_all(
        "Employee",
        filters={"company": company, "status": "Active"},
        fields=["name", "custom_nationality as nationality"],
    )

    saudi_count = sum(1 for e in employees if _is_saudi(e))
    non_saudi_count = len(employees) - saudi_count

    if USE_WEIGHTING:
        saudi_count, non_saudi_count = apply_weighting(saudi_count, non_saudi_count, employees)

    total = saudi_count + non_saudi_count
    percent = (saudi_count / total * 100) if total else 0

    return {
        "company": company,
        "saudi_count": saudi_count,
        "non_saudi_count": non_saudi_count,
        "total_count": total,
        "saudization_percent": round(percent, 2),
        "band": classify_band(percent),
        "bands_reference": NITAQAT_BANDS,
    }


@frappe.whitelist()
def simulate(company, saudi_delta=0, non_saudi_delta=0):
    """
    What-if: project the band after hiring/terminating the given
    number of Saudi/non-Saudi employees relative to the current
    headcount. Deltas can be negative (terminations).
    """
    saudi_delta = int(saudi_delta)
    non_saudi_delta = int(non_saudi_delta)

    current = get_snapshot(company)

    projected_saudi = max(current["saudi_count"] + saudi_delta, 0)
    projected_non_saudi = max(current["non_saudi_count"] + non_saudi_delta, 0)
    projected_total = projected_saudi + projected_non_saudi
    projected_percent = (projected_saudi / projected_total * 100) if projected_total else 0
    projected_band = classify_band(projected_percent)

    return {
        "current": current,
        "projected": {
            "saudi_count": projected_saudi,
            "non_saudi_count": projected_non_saudi,
            "total_count": projected_total,
            "saudization_percent": round(projected_percent, 2),
            "band": projected_band,
        },
        "band_changed": projected_band != current["band"],
    }