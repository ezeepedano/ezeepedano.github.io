from django.urls import path
from . import views

urlpatterns = [
    # Sales
    path('', views.sales_dashboard, name='sales_dashboard'),
    path('sale/<int:pk>/', views.sale_detail, name='sale_detail'),
    path('wholesale/add/', views.wholesale_create, name='wholesale_create'),
    path('upload/', views.upload_sales, name='upload_sales'),
    
    # Customers
    path('customers/', views.customer_list, name='customer_list'),
    path('customers/<int:pk>/', views.customer_detail, name='customer_detail'),
]
