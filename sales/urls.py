from django.urls import path
from . import views

urlpatterns = [
    # Sales
    path('', views.sales_dashboard, name='sales_dashboard'),
    path('sale/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('sale/<int:pk>/edit/', views.sale_edit, name='sale_edit'),
    path('add/', views.sale_create, name='sale_create'),
    path('tiendanube/add/', views.tiendanube_create, name='tiendanube_create'),
    path('upload/', views.upload_sales, name='upload_sales'),
    
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
    path('customers/<int:pk>/edit/', views.customer_edit, name='customer_edit'),
    path('customers/<int:pk>/delete/', views.customer_delete, name='customer_delete'),
    path('api/customer/<int:pk>/', views.customer_detail_api, name='customer_detail_api'),
    path('api/product/<int:pk>/', views.product_detail_api, name='product_detail_api'),
    path('api/customer/<int:customer_id>/history/', views.product_purchase_history_api, name='product_history_api'),
]
