# Copyright (c) 2024, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import getdate, add_days, getdate

def execute(filters=None):
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_data(filters)
    
    return columns, data

def get_columns():
    return [
        {
            "fieldname": "employee",
            "label": _("Employee"),
            "fieldtype": "Link",
            "options": "Employee",
            "width": 150
        },
        {
            "fieldname": "employee_name",
            "label": _("Employee Name"),
            "fieldtype": "Data",
            "width": 200
        },
        {
            "fieldname": "department",
            "label": _("Department"),
            "fieldtype": "Link",
            "options": "Department",
            "width": 150
        },
        {
            "fieldname": "date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 120
        },
        {
            "fieldname": "day",
            "label": _("Day"),
            "fieldtype": "Data",
            "width": 80
        },
        {
            "fieldname": "missing_type",
            "label": _("Missing Type"),
            "fieldtype": "Data",
            "width": 180
        },
        {
            "fieldname": "shift",
            "label": _("Assigned Shift"),
            "fieldtype": "Link",
            "options": "Shift Type",
            "width": 120
        },
        {
            "fieldname": "last_checkin",
            "label": _("Last Checkin Time"),
            "fieldtype": "Datetime",
            "width": 180
        }
    ]

def get_conditions(filters):
    conditions = ""
    
    if filters.get("company"):
        conditions += " AND emp.company = %(company)s"
    
    if filters.get("department"):
        conditions += " AND emp.department = %(department)s"
    
    if filters.get("employee"):
        conditions += " AND emp.name = %(employee)s"

    if not filters.get("include_no_checkin_required"):
        conditions += " AND (emp.custom_no_checkin_required = 0 OR emp.custom_no_checkin_required IS NULL)"
    
    return conditions

def get_data(filters):
    # Get date range from filters
    from_date = filters.get("from_date")
    to_date = filters.get("to_date")
    
    if not from_date or not to_date:
        frappe.msgprint(_("Please select From Date and To Date"))
        return []
    
    # Get list of holidays in the date range
    holidays = frappe.db.sql("""
        SELECT holiday_date 
        FROM `tabHoliday`
        WHERE holiday_date BETWEEN %(from_date)s AND %(to_date)s
        AND parent IN (
            SELECT hh.parent 
            FROM `tabHoliday List` hh
           
        )
    """, {
        "from_date": from_date,
        "to_date": to_date,
        "company": filters.get("company")
    }, as_dict=1)
    
    holiday_dates = [h["holiday_date"] for h in holidays]
    
    # Get all active employees
    employee_conditions = get_conditions(filters)
    
    employees = frappe.db.sql(f"""
        SELECT 
            emp.name as employee,
            emp.employee_name,
            emp.department,
            emp.default_shift as shift
        FROM `tabEmployee` emp
        WHERE emp.status = 'Active'
        {employee_conditions}
        ORDER BY emp.employee_name
    """, filters, as_dict=1)
    
    if not employees:
        frappe.msgprint(_("No active employees found for the selected criteria"))
        return []
    
    # For each date in range, check each employee's checkins
    result_data = []
    
    current_date = getdate(from_date)
    end_date = getdate(to_date)
    
    # Get all checkins in the date range for these employees
    employee_names = [e["employee"] for e in employees]
    
    if not employee_names:
        return []
    
    # Query all checkins at once for better performance
    checkins = frappe.db.sql("""
        SELECT 
            employee,
            DATE(time) as checkin_date,
            MIN(time) as first_checkin,
            MAX(time) as last_checkin,
            COUNT(*) as punch_count
        FROM `tabEmployee Checkin`
        WHERE employee IN %(employees)s
            AND DATE(time) BETWEEN %(from_date)s AND %(to_date)s
            AND log_type != 'Skip'
        GROUP BY employee, DATE(time)
    """, {
        "employees": employee_names,
        "from_date": from_date,
        "to_date": to_date
    }, as_dict=1)
    
    # Organize checkins by employee and date for quick lookup
    checkin_map = {}
    for chk in checkins:
        emp_date_key = f"{chk['employee']}|{chk['checkin_date']}"
        checkin_map[emp_date_key] = chk
    
    # Iterate through each date and employee
    while current_date <= end_date:
        date_str = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%A")
        
        # Skip holidays if the filter is enabled
        if filters.get("ignore_holidays") and date_str in holiday_dates:
            current_date = add_days(current_date, 1)
            continue
        
        for emp in employees:
            emp_date_key = f"{emp['employee']}|{date_str}"
            checkin_record = checkin_map.get(emp_date_key)
            
            missing_types = []
            last_checkin_time = None
            
            if not checkin_record:
                # No checkins at all
                missing_types.append(_("Check-in & Check-out"))
            else:
                # Only check for missing check-out if we have checkins
                # Determine if has check-out (simplified - assumes any checkin)
                # For more accurate check-out detection, you'd need to check shift end time
                if checkin_record.get("punch_count", 0) == 1:
                    missing_types.append(_("Check-out"))
                    last_checkin_time = checkin_record.get("first_checkin")
                else:
                    last_checkin_time = checkin_record.get("last_checkin")
            
            if missing_types:
                result_data.append({
                    "employee": emp["employee"],
                    "employee_name": emp["employee_name"],
                    "department": emp["department"],
                    "date": date_str,
                    "day": day_name,
                    "missing_type": ", ".join(missing_types),
                    "shift": emp.get("shift"),
                    "last_checkin": last_checkin_time
                })
        
        current_date = add_days(current_date, 1)
	
    if filters.get("missing_type") and filters.get("missing_type") != "All":
        result_data = [d for d in result_data if d["missing_type"] == filters.get("missing_type")]
    
    return result_data