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
    # Avanzados
    DashboardGMROIView,
    DashboardCCCView,
    DashboardCLVView,
    DashboardABCView,
    BusinessIntelligenceView,
    # Fase 3
    DashboardTargetsView,
    DashboardSalesForecastView,
    DashboardCashForecastView,
    DashboardUnifiedAlertsView,
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

    # Fase 3 — auto-targets, forecasts, unified alerts
    path('api/targets/',         DashboardTargetsView.as_view(),        name='api_targets'),
    path('api/sales-forecast/',  DashboardSalesForecastView.as_view(),  name='api_sales_forecast'),
    path('api/cash-forecast/',   DashboardCashForecastView.as_view(),   name='api_cash_forecast'),
    path('api/alerts/unified/',  DashboardUnifiedAlertsView.as_view(),  name='api_unified_alerts'),
    
    # Endpoints de exportación a Excel
    path('export/sales/', export_sales_to_excel, name='export_sales'),
    path('export/customers/', export_customers_to_excel, name='export_customers'),
    path('export/inventory/', export_inventory_to_excel, name='export_inventory'),
    
    # Vista HTML Dashboard BI
    path('bi/', BusinessIntelligenceView.as_view(), name='bi_dashboard'),
]
