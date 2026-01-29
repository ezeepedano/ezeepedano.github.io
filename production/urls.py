from django.urls import path
from . import views

urlpatterns = [
    # Orders
    path('orders/', views.ProductionOrderListView.as_view(), name='production_order_list'),
    path('orders/create/', views.ProductionOrderCreateView.as_view(), name='production_order_create'),
    path('orders/<int:pk>/update/', views.ProductionOrderUpdateView.as_view(), name='production_order_update'),
    path('ajax/boms/', views.get_boms_for_product, name='ajax_get_boms'),
    
    # Formulas (BOMs)
    path('formulas/', views.BillOfMaterialListView.as_view(), name='bom_list'),
    path('formulas/create/', views.BillOfMaterialCreateView.as_view(), name='bom_create'),
    path('formulas/<int:pk>/update/', views.BillOfMaterialUpdateView.as_view(), name='bom_update'),
]
