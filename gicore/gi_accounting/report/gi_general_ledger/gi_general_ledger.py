import frappe
from frappe import _
from frappe.utils import today, getdate, flt
from frappe.query_builder import DocType
from frappe.utils import cstr
import json

def execute(filters=None):
    """Main report execution"""
    if not filters:
        filters = {}
    
    columns = get_columns()
    data = get_data(filters)
    
    # Prepare chart if needed
    chart = get_chart(data)
    
    # Return report data
    return columns, data, None, chart

def get_columns():
    """Define report columns"""
    return [
        {
            "fieldname": "posting_date",
            "label": _("Date"),
            "fieldtype": "Date",
            "width": 90
        },
        {
            "fieldname": "voucher_no",
            "label": _("Voucher No"),
            "fieldtype": "Dynamic Link",
            "options": "voucher_type",
            "width": 130
        },
        {
            "fieldname": "voucher_type",
            "label": _("Voucher Type"),
            "fieldtype": "Data",
            "width": 100
        },
        {
            "fieldname": "account",
            "label": _("Account"),
            "fieldtype": "Link",
            "options": "Account",
            "width": 150
        },
        {
            "fieldname": "party",
            "label": _("Party"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "against",
            "label": _("Against"),
            "fieldtype": "Data",
            "width": 120
        },
        {
            "fieldname": "remarks",
            "label": _("Remarks"),
            "fieldtype": "Text",
            "width": 200
        },
        {
            "fieldname": "debit",
            "label": _("Debit"),
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "fieldname": "credit",
            "label": _("Credit"),
            "fieldtype": "Currency",
            "width": 110
        },
        {
            "fieldname": "balance",
            "label": _("Balance"),
            "fieldtype": "Currency",
            "width": 110
        }
    ]

def get_data(filters):
    """Fetch report data"""
    conditions = "1=1"
    values = {}
    
    # Dictionary access - use [] not .
    if filters.get("from_date"):
        conditions += " AND posting_date >= %(from_date)s"
        values["from_date"] = filters.get("from_date")
    if filters.get("to_date"):
        conditions += " AND posting_date <= %(to_date)s"
        values["to_date"] = filters.get("to_date")
    if filters.get("account"):
        conditions += " AND account = %(account)s"
        values["account"] = filters.get("account")
    if filters.get("cost_center"):
        conditions += " AND cost_center = %(cost_center)s"
        values["cost_center"] = filters.get("cost_center")
    if filters.get("project"):
        conditions += " AND project = %(project)s"
        values["project"] = filters.get("project")
    if filters.get("company"):
        conditions += " AND company = %(company)s"
        values["company"] = filters.get("company")
    
    query = f"""
        SELECT 
            posting_date, voucher_no, voucher_type, account,
            party_type, party, against, remarks, 
            debit, credit, company
        FROM `tabGL Entry`
        WHERE {conditions}
        ORDER BY posting_date, account, voucher_no
    """
    
    data = frappe.db.sql(query, values, as_dict=1)
    
    # Calculate running balance
    balance = 0
    for row in data:
        balance += flt(row.debit) - flt(row.credit)
        row.balance = balance
    
    return data

def get_chart(data):
    """Prepare chart data"""
    if not data:
        return None
    
    # Group by account for chart
    account_totals = {}
    for row in data:
        if row.account not in account_totals:
            account_totals[row.account] = {"debit": 0, "credit": 0}
        account_totals[row.account]["debit"] += flt(row.debit)
        account_totals[row.account]["credit"] += flt(row.credit)
    
    labels = list(account_totals.keys())
    debit_values = [account_totals[acc]["debit"] for acc in labels]
    credit_values = [account_totals[acc]["credit"] for acc in labels]
    
    return {
        "data": {
            "labels": labels[:10],  # Limit to top 10
            "datasets": [
                {
                    "name": "Debit",
                    "values": debit_values[:10],
                    "chartType": "bar"
                },
                {
                    "name": "Credit",
                    "values": credit_values[:10],
                    "chartType": "bar"
                }
            ]
        },
        "type": "bar",
        "title": "Account Activity"
    }

# ============ PRINT FUNCTIONALITY ============

@frappe.whitelist()
def get_print_html(filters):
    """API endpoint to get HTML for printing"""
    
    # Parse filters if passed as string
    if isinstance(filters, str):
        filters = json.loads(filters)
    
    frappe.log_error(f"Print filters received: {filters}", "General Ledger Print")
    
    # Get report data using the existing get_data function
    data = get_data(filters)
    
    # Get company details
    company = filters.get("company") or frappe.db.get_single_value("Global Defaults", "default_company")
    company_address = get_company_address(company)
    
    # Get currency
    currency = filters.get("currency") or "SAR"
    if company:
        company_currency = frappe.db.get_value("Company", company, "default_currency")
        if company_currency:
            currency = company_currency
    
    # Format entries with proper structure
    entries = []
    
    # Add opening balance if needed
    if filters.get("from_date"):
        opening_balance = get_opening_balance(filters)
        if opening_balance != 0:
            entries.append({
                "is_opening": True,
                "debit": opening_balance if opening_balance > 0 else 0,
                "credit": abs(opening_balance) if opening_balance < 0 else 0,
                "balance": opening_balance
            })
    
    # Group entries by account
    accounts_dict = {}
    for row in data:
        if row.account not in accounts_dict:
            accounts_dict[row.account] = []
        accounts_dict[row.account].append(row)
    
    # Build entries with group headers
    for account, rows in accounts_dict.items():
        # Add group header
        entries.append({
            "is_group_header": True,
            "account": account,
            "account_name": account,
            "account_currency": currency
        })
        
        # Calculate running balance for this account
        account_balance = 0
        
        # Add transaction rows
        for row in rows:
            account_balance += flt(row.debit) - flt(row.credit)
            entries.append({
                "posting_date": row.posting_date,
                "voucher_no": row.voucher_no,
                "voucher_type": row.voucher_type,
                "party": row.party or "",
                "against": row.against or "",
                "remarks": row.remarks or "",
                "debit": flt(row.debit),
                "credit": flt(row.credit),
                "balance": account_balance,
                "account_currency": currency
            })
        
        # Add closing balance for account
        if rows:
            account_total_debit = sum(flt(r.debit) for r in rows)
            account_total_credit = sum(flt(r.credit) for r in rows)
            entries.append({
                "is_closing_row": True,
                "account_name": account,
                "debit": account_total_debit,
                "credit": account_total_credit,
                "balance": account_balance
            })
    
    # Prepare context for Jinja template
    context = {
        "company": company,
        "company_address": company_address,
        "filters": filters,
        "entries": entries,
        "report_currency": currency,
        "print_date": today(),
        "printed_by": frappe.session.user_fullname or frappe.session.user
    }
    
    # Render the template
    html = render_print_template(context)
    return html

def render_print_template(context):
    """Render the HTML template"""
    
    template_html = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>General Ledger</title>
<style>
/* Reset & base */
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

:root {
  --ink: #111111;
  --ink-mid: #444444;
  --ink-light: #777777;
  --blue: #1A4F8A;
  --blue-light: #EBF1F9;
  --rule: #D8DDE3;
  --debit: #B72B27;
  --credit: #1A6B3A;
  --f-body: 8.4pt;
  --f-small: 7.5pt;
  --f-head: 7.8pt;
  --f-title: 13pt;
}

body {
  background: #FAFAFA;
  color: var(--ink);
  font-family: 'Inter', 'Segoe UI', Arial, sans-serif;
  font-size: var(--f-body);
  line-height: 1.35;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}

.gl-page {
  width: 100%;
  max-width: 297mm;
  margin: 0 auto;
  padding: 10mm;
  background: #fff;
}

/* Header */
.gl-header {
  display: grid;
  grid-template-columns: 1fr auto;
  align-items: start;
  gap: 12px;
  border-bottom: 2.5px solid var(--blue);
  padding-bottom: 8px;
  margin-bottom: 6px;
}

.gl-company-name {
  font-size: var(--f-title);
  font-weight: 700;
  color: var(--blue);
}

.gl-company-address {
  font-size: var(--f-small);
  color: var(--ink-light);
  margin-top: 2px;
}

.gl-report-label {
  font-size: 10pt;
  font-weight: 700;
  color: var(--blue);
  text-align: right;
  text-transform: uppercase;
}

/* Meta strip */
.gl-meta-strip {
  display: flex;
  flex-wrap: wrap;
  background: var(--blue-light);
  border: 1px solid #C9D9EE;
  border-radius: 4px;
  margin-bottom: 8px;
  overflow: hidden;
}

.gl-meta-item {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-right: 1px solid #C9D9EE;
  white-space: nowrap;
}

.gl-meta-item:last-child { border-right: none; }

.gl-meta-label {
  font-size: var(--f-small);
  font-weight: 600;
  color: var(--blue);
  text-transform: uppercase;
}

.gl-meta-val {
  font-size: var(--f-small);
  color: var(--ink);
  font-weight: 500;
}

/* Table */
.gl-table {
  width: 100%;
  border-collapse: collapse;
}

.gl-table thead tr {
  background: var(--blue);
  color: #fff;
}

.gl-table th, .gl-table td {
  padding: 5px;
  text-align: left;
  border-bottom: 1px solid var(--rule);
}

.gl-table td.num {
  text-align: right;
}

.debit-cell { color: var(--debit); font-weight: 500; }
.credit-cell { color: var(--credit); font-weight: 500; }
.balance-neg { color: var(--debit); font-weight: 600; }
.balance-pos { color: var(--credit); font-weight: 600; }

.group-header td {
  background: #F3F6FA;
  font-weight: 700;
  padding-top: 8px;
}

.closing-row td {
  background: #F3F6FA;
  font-weight: 700;
  border-top: 1.5px solid var(--blue);
}

.grand-total td {
  background: var(--blue);
  color: #fff;
  font-weight: 700;
}

/* Footer */
.gl-footer {
  margin-top: 10px;
  display: flex;
  justify-content: space-between;
  border-top: 1px solid var(--rule);
  padding-top: 5px;
}

.gl-footer-note, .gl-footer-sig {
  font-size: 7pt;
  color: var(--ink-light);
}

.gl-sig-line {
  width: 140px;
  border-top: 1px solid var(--rule);
  margin: 20px 0 3px auto;
}

@media print {
  @page { size: A4 landscape; margin: 8mm; }
  .gl-page { padding: 0; }
  .gl-table thead { display: table-header-group; }
}
</style>
</head>
<body>
<div class="gl-page">

  <!-- Header -->
  <div class="gl-header">
    <div>
      <div class="gl-company-name">{{ company }}</div>
      <div class="gl-company-address">{{ company_address }}</div>
    </div>
    <div>
      <div class="gl-report-label">General Ledger</div>
      <div style="font-size:7pt;text-align:right;margin-top:3px;">
        Printed: {{ print_date }} | {{ printed_by }}
      </div>
    </div>
  </div>

  <!-- Meta strip -->
  <div class="gl-meta-strip">
    <div class="gl-meta-item">
      <span class="gl-meta-label">Period</span>
      <span class="gl-meta-val">{{ filters.from_date }} — {{ filters.to_date }}</span>
    </div>
    {% if filters.account %}
    <div class="gl-meta-item">
      <span class="gl-meta-label">Account</span>
      <span class="gl-meta-val">{{ filters.account }}</span>
    </div>
    {% endif %}
    <div class="gl-meta-item">
      <span class="gl-meta-label">Currency</span>
      <span class="gl-meta-val">{{ report_currency }}</span>
    </div>
  </div>

  <!-- Table -->
  <table class="gl-table">
    <thead>
      <tr>
        <th>Date</th>
        <th>Voucher No.</th>
        <th>Type</th>
        <th>Party</th>
        <th>Against</th>
        <th>Remarks</th>
        <th class="num">Debit</th>
        <th class="num">Credit</th>
        <th class="num">Balance</th>
      </tr>
    </thead>
    <tbody>
      {% set ns = namespace(grand_debit=0, grand_credit=0) %}
      
      {% for entry in entries %}
        {% if entry.is_group_header %}
        <tr class="group-header">
          <td colspan="9"><strong>{{ entry.account_name }}</strong></td>
        </tr>
        
        {% elif entry.is_opening %}
        <tr>
          <td colspan="6"><em>Opening Balance</em></td>
          <td class="num">{% if entry.debit %}{{ '{:,.2f}'.format(entry.debit) }}{% else %}—{% endif %}</td>
          <td class="num">{% if entry.credit %}{{ '{:,.2f}'.format(entry.credit) }}{% else %}—{% endif %}</td>
          <td class="num {% if entry.balance < 0 %}balance-neg{% elif entry.balance > 0 %}balance-pos{% endif %}">
            {{ '{:,.2f}'.format(entry.balance|abs) }}
            {% if entry.balance < 0 %} Cr{% elif entry.balance > 0 %} Dr{% endif %}
          </td>
        </tr>
        
        {% elif entry.is_closing_row %}
        {% set ns.grand_debit = ns.grand_debit + (entry.debit or 0) %}
        {% set ns.grand_credit = ns.grand_credit + (entry.credit or 0) %}
        <tr class="closing-row">
          <td colspan="6">Closing Balance — {{ entry.account_name }}</td>
          <td class="num">{% if entry.debit %}{{ '{:,.2f}'.format(entry.debit) }}{% else %}—{% endif %}</td>
          <td class="num">{% if entry.credit %}{{ '{:,.2f}'.format(entry.credit) }}{% else %}—{% endif %}</td>
          <td class="num {% if entry.balance < 0 %}balance-neg{% elif entry.balance > 0 %}balance-pos{% endif %}">
            {{ '{:,.2f}'.format(entry.balance|abs) }}
            {% if entry.balance < 0 %} Cr{% elif entry.balance > 0 %} Dr{% endif %}
          </td>
        </tr>
        
        {% else %}
        <tr>
          <td>{{ entry.posting_date }}</td>
          <td>{{ entry.voucher_no }}</td>
          <td>{{ entry.voucher_type }}</td>
          <td>{{ entry.party or '—' }}</td>
          <td>{{ entry.against or '—' }}</td>
          <td>{{ entry.remarks or '—' }}</td>
          <td class="num {% if entry.debit > 0 %}debit-cell{% endif %}">
            {% if entry.debit > 0 %}{{ '{:,.2f}'.format(entry.debit) }}{% else %}—{% endif %}
          </td>
          <td class="num {% if entry.credit > 0 %}credit-cell{% endif %}">
            {% if entry.credit > 0 %}{{ '{:,.2f}'.format(entry.credit) }}{% else %}—{% endif %}
          </td>
          <td class="num {% if entry.balance < 0 %}balance-neg{% elif entry.balance > 0 %}balance-pos{% endif %}">
            {{ '{:,.2f}'.format(entry.balance|abs) }}
            {% if entry.balance < 0 %} Cr{% elif entry.balance > 0 %} Dr{% endif %}
          </td>
        </tr>
        {% endif %}
      {% endfor %}
    </tbody>
    
    <tfoot>
      <tr class="grand-total">
        <td colspan="6"><strong>GRAND TOTAL</strong></td>
        <td class="num">{{ '{:,.2f}'.format(ns.grand_debit) }}</td>
        <td class="num">{{ '{:,.2f}'.format(ns.grand_credit) }}</td>
        <td class="num">
          {% set net = ns.grand_debit - ns.grand_credit %}
          {{ '{:,.2f}'.format(net|abs) }}
          {% if net > 0 %} Dr{% elif net < 0 %} Cr{% endif %}
        </td>
      </tr>
    </tfoot>
  </table>

  <!-- Footer -->
  <div class="gl-footer">
    <div class="gl-footer-note">
      <strong>{{ company }}</strong><br>
      Generated on {{ print_date }} — All amounts in {{ report_currency }}
    </div>
    <div class="gl-footer-sig">
      <div class="gl-sig-line"></div>
      Authorised Signatory
    </div>
  </div>

</div>
</body>
</html>
    """
    
    return frappe.render_template(template_html, context)

def get_company_address(company):
    """Get company address as string - Fixed version"""
    if not company:
        return ""
    
    try:
        # Method 1: Get address from Dynamic Link
        address = frappe.db.sql("""
            SELECT 
                addr.address_line1, addr.address_line2, 
                addr.city, addr.country
            FROM `tabAddress` addr
            INNER JOIN `tabDynamic Link` dl ON dl.parent = addr.name
            WHERE dl.link_doctype = 'Company' 
                AND dl.link_name = %s
                AND addr.is_primary_address = 1
            LIMIT 1
        """, company, as_dict=1)
        
        if address and len(address) > 0:
            parts = [
                address[0].get("address_line1", ""),
                address[0].get("address_line2", ""),
                address[0].get("city", ""),
                address[0].get("country", "")
            ]
            return ", ".join([p for p in parts if p])
        
        # Method 2: Get company's default address
        address = frappe.db.get_value("Company", company, "default_company_address")
        if address:
            addr = frappe.get_doc("Address", address)
            parts = [addr.address_line1, addr.address_line2, addr.city, addr.country]
            return ", ".join([p for p in parts if p])
        
    except Exception as e:
        frappe.log_error(f"Error getting company address: {str(e)}", "General Ledger Print")
    
    # Fallback: return company name only
    return company

def get_opening_balance(filters):
    """Calculate opening balance before from_date"""
    conditions = "1=1"
    values = {}
    
    if filters.get("from_date"):
        conditions += " AND posting_date < %(from_date)s"
        values["from_date"] = filters.get("from_date")
    if filters.get("account"):
        conditions += " AND account = %(account)s"
        values["account"] = filters.get("account")
    if filters.get("cost_center"):
        conditions += " AND cost_center = %(cost_center)s"
        values["cost_center"] = filters.get("cost_center")
    if filters.get("project"):
        conditions += " AND project = %(project)s"
        values["project"] = filters.get("project")
    if filters.get("company"):
        conditions += " AND company = %(company)s"
        values["company"] = filters.get("company")
    
    query = f"""
        SELECT SUM(debit) - SUM(credit) as balance
        FROM `tabGL Entry`
        WHERE {conditions}
    """
    
    result = frappe.db.sql(query, values, as_dict=1)
    return flt(result[0].balance if result else 0)