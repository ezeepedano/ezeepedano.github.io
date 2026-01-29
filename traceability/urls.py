from django.urls import path
from . import views

app_name = 'traceability'

urlpatterns = [
    # Stock Management
    path('stock/', views.StockListView.as_view(), name='stock_list'),
    path('purchase/create/', views.PurchaseCreateView.as_view(), name='purchase_create'),
    
    # Production
    path('production/create/', views.ProductionCreateView.as_view(), name='production_create'),
    path('production/history/', views.ProductionHistoryView.as_view(), name='production_history'),
    path('production/<int:pk>/', views.ProductionDetailView.as_view(), name='production_detail'),
    
    # Alerts
    path('alerts/', views.AlertListView.as_view(), name='alert_list'),
]
