from django.urls import path
from . import views

urlpatterns = [
    # Sales
    path('', views.sales_dashboard, name='sales_dashboard'),
    path('sale/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('add/', views.sale_create, name='sale_create'),
    path('tiendanube/add/', views.tiendanube_create, name='tiendanube_create'),
    path('upload/', views.upload_sales, name='upload_sales'),
    
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/add/', views.customer_create, name='customer_create'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
]
