from django.urls import path
from . import views
from . import pdf_views

urlpatterns = [
    # Reports Hub
    path('reports/', pdf_views.reports_hub, name='reports_hub'),

    # Orders
    path('orders/', views.ProductionOrderListView.as_view(), name='production_order_list'),
    path('orders/create/', views.ProductionOrderCreateView.as_view(), name='production_order_create'),
    path('orders/<int:pk>/update/', views.ProductionOrderUpdateView.as_view(), name='production_order_update'),
    path('orders/bulk-delete/', views.bulk_delete_orders, name='bulk_delete_orders'),
    path('ajax/boms/', views.get_boms_for_product, name='ajax_get_boms'),
    path('api/bom/<int:pk>/', views.bom_detail_api, name='bom_detail_api'),
    path('api/bom/<int:bom_id>/validate-stock/', views.stock_validation_api, name='stock_validation_api'),
    
    # Formulas (BOMs)
    path('formulas/', views.BillOfMaterialListView.as_view(), name='bom_list'),
    path('formulas/bulk-delete/', views.bulk_delete_boms, name='bulk_delete_boms'),
    path('formulas/create/', views.BillOfMaterialCreateView.as_view(), name='bom_create'),
    path('formulas/<int:pk>/update/', views.BillOfMaterialUpdateView.as_view(), name='bom_update'),

    # PDF Reports
    path('reports/orden/<int:pk>/', pdf_views.production_order_pdf, name='report_production_order'),
    path('reports/mrp/<int:bom_id>/', pdf_views.mrp_explosion_pdf, name='report_mrp_explosion'),
    path('reports/trazabilidad/lote/<int:batch_id>/', pdf_views.traceability_backward_pdf, name='report_traceability_backward'),
    path('reports/trazabilidad/mp/<int:lot_id>/', pdf_views.traceability_forward_pdf, name='report_traceability_forward'),
    path('reports/coa/<int:batch_id>/', pdf_views.coa_pdf, name='report_coa'),
    path('reports/fefo/', pdf_views.fefo_expiry_pdf, name='report_fefo_expiry'),
    path('reports/kardex/<int:ingredient_id>/', pdf_views.kardex_pdf, name='report_kardex'),
    path('reports/rendimiento/<int:batch_id>/', pdf_views.batch_yield_pdf, name='report_batch_yield'),
]

