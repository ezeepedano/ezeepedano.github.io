from django.urls import path
from . import views
from . import quotation_views

urlpatterns = [
    # Sales
    path('', views.sales_dashboard, name='sales_dashboard'),
    path('sale/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('sale/<int:pk>/edit/', views.sale_edit, name='sale_edit'),
    path('sale/<int:pk>/pdf/', views.sale_pdf, name='sale_pdf'),
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

    # Quotations / Presupuestos
    path('quotations/', quotation_views.quotation_list, name='quotation_list'),
    path('quotations/create/', quotation_views.quotation_create, name='quotation_create'),
    path('quotations/<int:pk>/edit/', quotation_views.quotation_edit, name='quotation_edit'),
    path('quotations/<int:pk>/delete/', quotation_views.quotation_delete, name='quotation_delete'),
    path('quotations/<int:pk>/pdf/', quotation_views.quotation_pdf, name='quotation_pdf'),
    path('quotations/<int:pk>/duplicate/', quotation_views.quotation_duplicate, name='quotation_duplicate'),
    path('quotations/<int:pk>/to-sale/', quotation_views.quotation_to_sale, name='quotation_to_sale'),
    path('api/quotation/product/<int:pk>/', quotation_views.product_price_api_quotation, name='quotation_product_api'),

    # Company Config
    path('config/', quotation_views.company_config, name='company_config'),

    # Returns / Devoluciones
    path('returns/', views.return_list, name='return_list'),
]

