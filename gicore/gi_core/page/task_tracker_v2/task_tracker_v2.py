import frappe
from frappe.utils import nowdate

@frappe.whitelist()
def get_tasks(search="", project="", task_type="", status="", priority="", page=1, page_size=15):
    """
    Get tasks with filters and return counts based on current filters
    """
    # Convert page and page_size to integers (they come as strings from frontend)
    try:
        page = int(page)
    except (TypeError, ValueError):
        page = 1
    
    try:
        page_size = int(page_size)
    except (TypeError, ValueError):
        page_size = 15
    
    filters = {}
    
    if project:
        filters["project"] = project
    if task_type:
        filters["type"] = task_type
    if status:
        filters["status"] = status
    if priority:
        filters["priority"] = priority
    
    # Search filter
    if search:
        filters["subject"] = ["like", f"%{search}%"]
    
    # Calculate offset for pagination
    offset = (page - 1) * page_size
    
    # Get paginated tasks
    tasks = frappe.get_list(
        "Task",
        filters=filters,
        fields=["name", "subject", "status", "priority", "project", "type", 
                "exp_end_date", "progress", "assigned_to"],
        start=offset,
        page_length=page_size,
        order_by="creation desc"
    )
    
    # Get total count with filters
    total = frappe.db.count("Task", filters=filters)
    
    # Get status counts based on current filters
    status_counts = {
        "total": total,
        "open": frappe.db.count("Task", filters={**filters, "status": "Open"}),
        "working": frappe.db.count("Task", filters={**filters, "status": "Working"}),
        "pending_review": frappe.db.count("Task", filters={**filters, "status": "Pending Review"}),
        "overdue": frappe.db.count("Task", filters={**filters, "status": "Overdue"}),
        "cancelled": frappe.db.count("Task", filters={**filters, "status": "Cancelled"}),
        "completed": frappe.db.count("Task", filters={**filters, "status": "Completed"}),
    }
    
    # Get task type counts based on current filters
    # First, get all unique task types
    all_types = frappe.db.get_all("Task", 
                                   filters={"type": ["!=", ""]}, 
                                   fields=["type"], 
                                   group_by="type",
                                   pluck="type")
    
    type_counts = {}
    for t in all_types:
        type_filters = {**filters, "type": t}
        type_counts[t] = frappe.db.count("Task", filters=type_filters)
    
    # Get priority counts based on current filters
    priority_counts = {
        "low": frappe.db.count("Task", filters={**filters, "priority": "Low"}),
        "medium": frappe.db.count("Task", filters={**filters, "priority": "Medium"}),
        "high": frappe.db.count("Task", filters={**filters, "priority": "High"}),
        "urgent": frappe.db.count("Task", filters={**filters, "priority": "Urgent"}),
    }
    
    return {
        "tasks": tasks,
        "total": total,
        "status_counts": status_counts,
        "type_counts": type_counts,
        "priority_counts": priority_counts,
    }


@frappe.whitelist()
def get_filter_options():
    """
    Get available filter options (projects and task types)
    """
    projects = frappe.get_all("Project", fields=["name", "project_name"], limit_page_length=500)
    task_types = frappe.db.get_all("Task", 
                                    filters={"type": ["!=", ""]}, 
                                    fields=["type"], 
                                    group_by="type",
                                    pluck="type")
    
    return {
        "projects": projects,
        "task_types": task_types
    }


@frappe.whitelist()
def update_task_status(task_name, status):
    """
    Update task status
    """
    try:
        task = frappe.get_doc("Task", task_name)
        task.status = status
        task.save()
        frappe.db.commit()
        return {"success": True, "message": f"Task status updated to {status}"}
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def get_task_detail(task_name):
    """
    Get detailed task information for the review panel
    """
    try:
        task = frappe.get_doc("Task", task_name)
        
        # Get comments
        comments = frappe.get_all("Comment", 
                                   filters={"reference_doctype": "Task", 
                                           "reference_name": task_name,
                                           "comment_type": "Comment"},
                                   fields=["content", "owner", "creation"],
                                   order_by="creation desc")
        
        # Format comments
        formatted_comments = []
        for comment in comments:
            formatted_comments.append({
                "content": comment.content,
                "comment_by": frappe.db.get_value("User", comment.owner, "full_name") or comment.owner,
                "creation": comment.creation
            })
        
        # Get assignees
        assignees = []
        if task._assign:
            import json
            try:
                assigned = json.loads(task._assign)
                for user in assigned:
                    user_name = frappe.db.get_value("User", user, "full_name") or user
                    assignees.append(user_name)
            except:
                pass
        
        return {
            "subject": task.subject,
            "status": task.status,
            "priority": task.priority,
            "project": task.project,
            "type": task.type,
            "exp_start_date": task.exp_start_date.strftime("%Y-%m-%d") if task.exp_start_date else None,
            "exp_end_date": task.exp_end_date.strftime("%Y-%m-%d") if task.exp_end_date else None,
            "progress": task.progress or 0,
            "parent_task": task.parent_task,
            "description": task.description,
            "assignees": assignees,
            "comments": formatted_comments
        }
    except Exception as e:
        frappe.log_error(f"Error getting task detail: {str(e)}", "Task Tracker")
        return {
            "subject": "Error loading task",
            "status": "Open",
            "priority": "Medium",
            "project": "",
            "type": "",
            "exp_start_date": None,
            "exp_end_date": None,
            "progress": 0,
            "parent_task": "",
            "description": f"Error loading task details: {str(e)}",
            "assignees": [],
            "comments": []
        }


@frappe.whitelist()
def create_task(subject, project="", task_type="", priority="Medium", description=""):
    """
    Create a new task
    """
    try:
        task = frappe.get_doc({
            "doctype": "Task",
            "subject": subject,
            "project": project,
            "type": task_type,
            "priority": priority,
            "description": description,
            "status": "Open"
        })
        task.insert()
        frappe.db.commit()
        return {"success": True, "subject": task.subject, "name": task.name}
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "message": str(e)}


@frappe.whitelist()
def add_comment(task_name, comment):
    """
    Add a comment to a task
    """
    try:
        task = frappe.get_doc("Task", task_name)
        task.add_comment(text=comment)
        frappe.db.commit()
        return {"success": True}
    except Exception as e:
        frappe.db.rollback()
        return {"success": False, "message": str(e)}