import frappe
from frappe import _
from frappe.utils import getdate, date_diff, add_days, now_datetime
import json

WEEKDAY_NAMES = {
    0: "Monday",
    1: "Tuesday",
    2: "Wednesday",
    3: "Thursday",
    4: "Friday",
    5: "Saturday",
    6: "Sunday",
}


# ─────────────────────────────────────────────
#  Main report entry point
# ─────────────────────────────────────────────

def execute(filters=None):
    filters = frappe._dict(filters or {})
    validate_filters(filters)

    from_date = getdate(filters.from_date)
    to_date = getdate(filters.to_date)

    delta = date_diff(to_date, from_date)
    if delta > 30:
        frappe.throw(_("Date range cannot exceed 30 days."))

    date_list = build_date_list(from_date, to_date)
    columns = get_columns(date_list)

    employees = get_employees(filters)
    if not employees:
        return columns, []

    employee_ids = [e.name for e in employees]
    checkins = get_checkins(employee_ids, from_date, to_date)
    checkin_map = build_checkin_map(checkins)
    data = build_data(employees, date_list, checkin_map, filters)

    return columns, data


# ─────────────────────────────────────────────
#  Whitelisted API — called by the Print button
# ─────────────────────────────────────────────

@frappe.whitelist()
def get_print_html(filters):
    """
    Generates and returns the full print-ready HTML for the report.
    Called via frappe.call() from the JS Print button.
    """
    if isinstance(filters, str):
        filters = json.loads(filters)

    filters = frappe._dict(filters)
    validate_filters(filters)

    from_date = getdate(filters.from_date)
    to_date = getdate(filters.to_date)

    delta = date_diff(to_date, from_date)
    if delta > 30:
        frappe.throw(_("Date range cannot exceed 30 days."))

    date_list = build_date_list(from_date, to_date)
    employees = get_employees(filters)
    employee_ids = [e.name for e in employees] if employees else []
    checkins = get_checkins(employee_ids, from_date, to_date) if employee_ids else []
    checkin_map = build_checkin_map(checkins)
    data = build_data(employees, date_list, checkin_map, filters)

    html = render_print_html(filters, date_list, data)
    return html


# ─────────────────────────────────────────────
#  Print HTML renderer
# ─────────────────────────────────────────────

def render_print_html(filters, date_list, data):
    from_date = filters.get("from_date", "")
    to_date = filters.get("to_date", "")
    company = filters.get("company", "")
    department = filters.get("department", "")
    printed_at = now_datetime().strftime("%d-%m-%Y %H:%M")
    user = frappe.session.user

    # Build meta line
    meta_parts = [f"<span><strong>Period:</strong> {from_date} &ndash; {to_date}</span>"]
    if company:
        meta_parts.append(f"<span><strong>Company:</strong> {company}</span>")
    if department:
        meta_parts.append(f"<span><strong>Department:</strong> {department}</span>")
    meta_parts.append(f"<span><strong>Printed:</strong> {printed_at}</span>")
    meta_html = " ".join(meta_parts)

    # Build table header row
    header_cells = ""
    for d in date_list:
        weekday = WEEKDAY_NAMES[d.weekday()]
        label = f"{weekday}<br>{d.strftime('%d-%m')}"
        header_cells += f'<th class="day-col"><div class="rotate">{label}</div></th>\n'

    summary_headers = ["Present", "Absent", "One Checkin", "Total Hrs"]
    for sh in summary_headers:
        header_cells += f'<th class="summary-col"><div class="rotate">{sh}</div></th>\n'

    # Build table body rows
    body_rows = ""
    for row in data:
        cells = f'<td class="emp-col">{frappe.utils.escape_html(row["employee_name"])}</td>\n'
        cells += f'<td class="dept-col">{frappe.utils.escape_html(row.get("department", ""))}</td>\n'

        for d in date_list:
            field = f"day_{d.strftime('%Y%m%d')}"
            val = row.get(field, "")
            if val == "A":
                cell_content = '<span class="status-A">A</span>'
            elif val == "O":
                cell_content = '<span class="status-O">O</span>'
            elif val:
                cell_content = f'<span class="status-H">{frappe.utils.escape_html(val)}</span>'
            else:
                cell_content = "&mdash;"
            cells += f'<td class="day-cell">{cell_content}</td>\n'

        absent_style = ' style="color:#e74c3c;"' if row["total_absent"] > 0 else ""
        one_style = ' style="color:#e67e22;"' if row["total_one_checkin"] > 0 else ""
        cells += f'<td class="summary-cell">{row["total_present"]}</td>\n'
        cells += f'<td class="summary-cell"{absent_style}>{row["total_absent"]}</td>\n'
        cells += f'<td class="summary-cell"{one_style}>{row["total_one_checkin"]}</td>\n'
        cells += f'<td class="summary-cell">{row["total_hours"]:.1f}</td>\n'

        body_rows += f"<tr>{cells}</tr>\n"

    if not body_rows:
        body_rows = f'<tr><td colspan="100" style="text-align:center;padding:20px;color:#888;">{_("No data found.")}</td></tr>'

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Employee Attendance Summary</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 9pt;
    color: #1a1a1a;
    background: #fff;
    padding: 16px;
  }}
  .no-print {{ display: block; }}
  @media print {{ .no-print {{ display: none !important; }} }}

  /* ── Print button (visible on screen only) ── */
  .print-action-bar {{
    display: flex;
    justify-content: flex-end;
    margin-bottom: 14px;
  }}
  .btn-print {{
    background: #2c3e50;
    color: #fff;
    border: none;
    padding: 8px 22px;
    font-size: 10pt;
    border-radius: 5px;
    cursor: pointer;
    letter-spacing: 0.4px;
  }}
  .btn-print:hover {{ background: #1a252f; }}

  /* ── Header ── */
  .report-header {{
    text-align: center;
    margin-bottom: 12px;
    padding-bottom: 8px;
    border-bottom: 2px solid #2c3e50;
  }}
  .report-header h2 {{
    font-size: 16pt;
    font-weight: 700;
    color: #2c3e50;
  }}
  .report-header .meta {{
    font-size: 8.5pt;
    color: #555;
    margin-top: 4px;
  }}
  .report-header .meta span {{ margin: 0 8px; }}

  /* ── Table ── */
  .attendance-table {{
    width: 100%;
    border-collapse: collapse;
    table-layout: fixed;
  }}
  .attendance-table th.emp-col,
  .attendance-table td.emp-col {{
    width: 150px; min-width: 140px;
    text-align: left; padding: 4px 6px;
    font-weight: 600; border: 1px solid #ccc;
    background: #f4f6f8; vertical-align: middle;
  }}
  .attendance-table th.dept-col,
  .attendance-table td.dept-col {{
    width: 110px; min-width: 100px;
    font-size: 8pt; text-align: left;
    padding: 4px 5px; border: 1px solid #ccc;
    background: #f4f6f8; vertical-align: middle; color: #555;
  }}
  .attendance-table th.day-col {{
    width: 32px; min-width: 28px; max-width: 36px;
    height: 90px; padding: 4px 2px;
    border: 1px solid #ccc;
    background: #2c3e50; color: #fff;
    vertical-align: bottom; text-align: center;
  }}
  .attendance-table th.day-col .rotate {{
    writing-mode: vertical-rl;
    text-orientation: mixed;
    transform: rotate(180deg);
    display: inline-block;
    font-size: 7.5pt; font-weight: 600;
    line-height: 1.2; white-space: nowrap;
  }}
  .attendance-table th.summary-col {{
    width: 40px; height: 90px; padding: 4px 2px;
    border: 1px solid #ccc;
    background: #34495e; color: #fff;
    vertical-align: bottom; text-align: center;
  }}
  .attendance-table th.summary-col .rotate {{
    writing-mode: vertical-rl;
    text-orientation: mixed;
    transform: rotate(180deg);
    display: inline-block;
    font-size: 7.5pt; font-weight: 600;
    white-space: nowrap;
  }}
  .attendance-table td.day-cell {{
    text-align: center; font-size: 8pt; font-weight: 600;
    border: 1px solid #ddd; padding: 3px 1px; vertical-align: middle;
  }}
  .attendance-table td.summary-cell {{
    text-align: center; font-size: 8pt; font-weight: 700;
    border: 1px solid #ddd; padding: 3px 2px;
    vertical-align: middle; background: #f9f9f9;
  }}
  .attendance-table tbody tr:nth-child(even) td.emp-col,
  .attendance-table tbody tr:nth-child(even) td.dept-col {{ background: #eaf0f7; }}
  .attendance-table tbody tr:nth-child(even) td.day-cell {{ background: #fafcfe; }}

  /* ── Status badges ── */
  .status-A {{
    color: #fff; background-color: #e74c3c;
    border-radius: 3px; padding: 1px 5px; font-size: 8pt;
  }}
  .status-O {{
    color: #fff; background-color: #e67e22;
    border-radius: 3px; padding: 1px 5px; font-size: 8pt;
  }}
  .status-H {{
    color: #fff; background-color: #27ae60;
    border-radius: 3px; padding: 1px 5px; font-size: 8pt;
  }}

  /* ── Legend ── */
  .legend {{
    margin-top: 14px; display: flex;
    gap: 20px; align-items: center; font-size: 8pt;
  }}
  .legend-badge {{
    padding: 2px 8px; 
    border-radius: 3px;
    font-weight: 700; color: #fff; font-size: 8pt;
  }}

  /* ── Footer ── */
  .print-footer {{
    margin-top: 16px; font-size: 7.5pt;
    color: #888; text-align: right;
    border-top: 1px solid #ddd; padding-top: 5px;
  }}

  @media print {{
    body {{ padding: 8px; font-size: 8pt; }}
    .attendance-table {{ page-break-inside: auto; }}
    tr {{ page-break-inside: avoid; page-break-after: auto; }}
  }}
</style>
</head>
<body>

<div class="no-print print-action-bar">
  <button class="btn-print" onclick="window.print()">&#128424; Print</button>
</div>

<div class="report-header">
  <h2>Employee Attendance Summary</h2>
  <div class="meta">{meta_html}</div>
</div>

<table class="attendance-table">
  <thead>
    <tr>
      <th class="emp-col">Employee</th>
      <th class="dept-col">Department</th>
      {header_cells}
    </tr>
  </thead>
  <tbody>
    {body_rows}
  </tbody>
</table>

<div class="legend">
  <strong>Legend:</strong>
  <div style="display:flex;align-items:center;gap:5px;">
    <span class="legend-badge" style="background:#27ae60;">7.5h</span> Present (working hours)
  </div>
  <div style="display:flex;align-items:center;gap:5px;">
    <span class="legend-badge" style="background:#e74c3c;">A</span> Absent
  </div>
  <div style="display:flex;align-items:center;gap:5px;">
    <span class="legend-badge" style="background:#e67e22;">O</span> Only one check-in recorded
  </div>
</div>

<div class="print-footer">
  Employee Attendance Summary &mdash; Generated by {frappe.utils.escape_html(user)} on {printed_at}
</div>

</body>
</html>"""

    return html


# ─────────────────────────────────────────────
#  Shared helpers
# ─────────────────────────────────────────────

def validate_filters(filters):
    if not filters.from_date:
        frappe.throw(_("Please set From Date"))
    if not filters.to_date:
        frappe.throw(_("Please set To Date"))
    if getdate(filters.from_date) > getdate(filters.to_date):
        frappe.throw(_("From Date cannot be after To Date"))


def build_date_list(from_date, to_date):
    date_list = []
    d = from_date
    while d <= to_date:
        date_list.append(d)
        d = add_days(d, 1)
    return date_list


def get_columns(date_list):
    columns = [
        {
            "fieldname": "employee",
            "label": _("Employee ID"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 250,
        },
        # {
        #     "fieldname": "employee_name",
        #     "label": _("Employee Name"),
        #     "fieldtype": "Data",
        #     "width": 160,
        # },
        {
            "fieldname": "department",
            "label": _("Department"),
            "fieldtype": "Data",
            "width": 130,
        },
    ]

    for d in date_list:
        weekday = WEEKDAY_NAMES[d.weekday()]
        col_label = f"{weekday[:3]}{d.strftime('%d-%m')}"
        columns.append(
            {
                "fieldname": f"day_{d.strftime('%Y%m%d')}",
                "label": col_label,
                "fieldtype": "Data",
                "width": 90,
            }
        )

    columns += [
        {"fieldname": "total_present",     "label": _("Present"),     "fieldtype": "Int",   "width": 70},
        {"fieldname": "total_absent",      "label": _("Absent"),      "fieldtype": "Int",   "width": 70},
        {"fieldname": "total_one_checkin", "label": _("One Checkin"), "fieldtype": "Int",   "width": 90},
        {"fieldname": "total_hours",       "label": _("Total Hours"), "fieldtype": "Float", "precision": 2, "width": 100},
    ]
    return columns


def get_employees(filters):
    conditions = {"status": "Active"}
    if filters.get("company"):
        conditions["company"] = filters.company
    if filters.get("department"):
        conditions["department"] = filters.department
    if filters.get("employee"):
        conditions["name"] = filters.employee

    return frappe.get_all(
        "Employee",
        filters=conditions,
        fields=["name", "employee_name", "department", "company"],
        order_by="employee_name asc",
    )


def get_checkins(employee_ids, from_date, to_date):
    return frappe.db.sql(
        """
        SELECT
            employee,
            DATE(time) AS checkin_date,
            MIN(time)  AS first_checkin,
            MAX(time)  AS last_checkout,
            COUNT(*)   AS checkin_count
        FROM `tabEmployee Checkin`
        WHERE
            employee IN %(employees)s
            AND DATE(time) BETWEEN %(from_date)s AND %(to_date)s
        GROUP BY employee, DATE(time)
        """,
        {"employees": employee_ids, "from_date": from_date, "to_date": to_date},
        as_dict=True,
    )


def build_checkin_map(checkins):
    checkin_map = {}
    for row in checkins:
        emp = row.employee
        date_str = str(row.checkin_date)
        if emp not in checkin_map:
            checkin_map[emp] = {}

        hours = 0.0
        if row.checkin_count >= 2:
            diff = row.last_checkout - row.first_checkin
            hours = round(diff.total_seconds() / 3600, 2)

        checkin_map[emp][date_str] = {
            "count": row.checkin_count,
            "hours": hours,
            "first": row.first_checkin,
            "last": row.last_checkout,
        }
    return checkin_map


def build_data(employees, date_list, checkin_map, filters):
    data = []
    hours_less_than = filters.get("hours_less_than")
    status_filter = filters.get("status_filter")

    for emp in employees:
        row = {
            "employee": emp.name,
            "employee_name": emp.employee_name,
            "department": emp.department or "",
        }

        total_present = 0
        total_absent = 0
        total_one_checkin = 0
        total_hours = 0.0

        for d in date_list:
            field = f"day_{d.strftime('%Y%m%d')}"
            date_str = str(d)
            emp_day = checkin_map.get(emp.name, {}).get(date_str)

            if emp_day is None:
                row[field] = "A"
                total_absent += 1
            elif emp_day["count"] == 1:
                row[field] = "O"
                total_one_checkin += 1
            else:
                h = emp_day["hours"]
                row[field] = f"{h:.1f}"
                total_present += 1
                total_hours += h

        row["total_present"] = total_present
        row["total_absent"] = total_absent
        row["total_one_checkin"] = total_one_checkin
        row["total_hours"] = round(total_hours, 2)

        if status_filter == "Absent"      and total_absent == 0:       continue
        if status_filter == "Present"     and total_present == 0:      continue
        if status_filter == "One Checkin" and total_one_checkin == 0:  continue

        if hours_less_than:
            try:
                if total_hours >= float(hours_less_than):
                    continue
            except ValueError:
                pass

        data.append(row)

    return data
