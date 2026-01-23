from django.urls import path
from .views import (
    ExecutiveDashboardView, 
    DashboardKPIsView,
    DashboardTrendsView,
    DashboardChannelView,
    DashboardFinanceView,
    DashboardRecentMovesView,
    DashboardAgingView,
    DashboardTopProductsView,
    DashboardStockAlertsView,
    DashboardCustomerView,
    # Nuevas vistas avanzadas
    DashboardGMROIView,
    DashboardCCCView,
    DashboardCLVView,
    DashboardABCView,
    BusinessIntelligenceView,
)
from .excel_exports import (
    export_sales_to_excel,
    export_customers_to_excel,
    export_inventory_to_excel,
)

urlpatterns = [
    path('', ExecutiveDashboardView.as_view(), name='executive_dashboard'),
    
    # API endpoints existentes
    path('api/kpis/', DashboardKPIsView.as_view(), name='api_kpis'),
    path('api/trends/', DashboardTrendsView.as_view(), name='api_trends'),
    path('api/channels/', DashboardChannelView.as_view(), name='api_channels'),
    path('api/finance/', DashboardFinanceView.as_view(), name='api_finance'),
    path('api/recent-moves/', DashboardRecentMovesView.as_view(), name='api_recent_moves'),
    path('api/aging/', DashboardAgingView.as_view(), name='api_aging'),
    path('api/top-products/', DashboardTopProductsView.as_view(), name='api_top_products'),
    path('api/stock-alerts/', DashboardStockAlertsView.as_view(), name='api_stock_alerts'),
    path('api/customers/', DashboardCustomerView.as_view(), name='api_customers'),
    
    # Nuevos endpoints para KPIs avanzados
    path('api/gmroi/', DashboardGMROIView.as_view(), name='api_gmroi'),
    path('api/ccc/', DashboardCCCView.as_view(), name='api_ccc'),
    path('api/clv/', DashboardCLVView.as_view(), name='api_clv'),
    path('api/abc/', DashboardABCView.as_view(), name='api_abc'),
    
    # Endpoints de exportación a Excel
    path('export/sales/', export_sales_to_excel, name='export_sales'),
    path('export/customers/', export_customers_to_excel, name='export_customers'),
    path('export/inventory/', export_inventory_to_excel, name='export_inventory'),
    
    # Vista HTML Dashboard BI
    path('bi/', BusinessIntelligenceView.as_view(), name='bi_dashboard'),
]
