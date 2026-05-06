import os
import re

files_to_restore = [
    "accounting/templates/accounting/journal_entry_list.html",
    "accounting/templates/accounting/trial_balance.html",
    "finance/templates/finance/dashboard_aging.html",
    "finance/templates/finance/dashboard_cashflow.html",
    "finance/templates/finance/fixed_cost_list.html",
    "hr/templates/hr/employee_list.html",
    "hr/templates/hr/payroll_list.html",
    "inventory/templates/inventory/ingredient_list.html",
    "inventory/templates/inventory/product_list.html",
    "production/templates/production/bom_list.html",
    "production/templates/production/order_list.html",
    "sales/templates/sales/customers/list.html",
    "sales/templates/sales/dashboard.html",
    "sales/templates/sales/quotation_list.html",
    "traceability/templates/traceability/stock_list.html",
]

link_html = """
            <a href="{% url 'executive_dashboard' %}" class="inline-flex items-center text-sm text-gray-500 hover:text-primary mt-2 transition-colors">
                <i class="fas fa-arrow-left mr-1"></i> Volver al Tablero
            </a>
"""

for fname in files_to_restore:
    path = os.path.join(r"C:\Users\Alex\OneDrive - alumnos.iua.edu.ar\JKGE 2025\ERP", fname)
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    pattern = re.compile(r'(<h[12][^>]*>.*?</p>(?:\s*{%[^%]*%}\s*<p[^>]*>.*?</p>\s*{%[^%]*%})?\s*)(</div>)', re.DOTALL)
    
    new_content, count = pattern.subn(r'\g<1>' + link_html + r'        \g<2>', content, count=1)
    
    if count == 0:
        print(f"Failed to match in {fname}")
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
