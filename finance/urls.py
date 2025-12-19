from django.urls import path
from . import views

urlpatterns = [
    # Monthly View (History)
    path('costs/', views.fixed_cost_list, name='fixed_cost_list'),
    path('costs/generate/', views.generate_monthly_expenses, name='generate_monthly_expenses'),
    path('costs/delete/', views.delete_monthly_expenses, name='delete_monthly_expenses'),
    path('costs/<int:pk>/toggle/', views.toggle_payment, name='toggle_payment'),

    # Definitions (Templates)
    path('definitions/', views.fixed_cost_definition_list, name='fixed_cost_definition_list'),
    path('definitions/create/', views.fixed_cost_create, name='fixed_cost_create'),
    path('definitions/<int:pk>/edit/', views.fixed_cost_edit, name='fixed_cost_edit'),
    path('definitions/<int:pk>/delete/', views.fixed_cost_delete, name='fixed_cost_delete'),
    
    # Purchases
    path('variable/new/', views.variable_expense_create, name='variable_expense_create'),
    path('purchases/create/', views.purchase_create, name='purchase_create'),
    # Assets
    path('assets/', views.asset_list, name='asset_list'),
    path('assets/create/', views.asset_create, name='asset_create'),
    path('assets/categories/<int:pk>/delete/', views.asset_category_delete, name='asset_category_delete'),
    path('assets/<int:pk>/', views.asset_detail, name='asset_detail'),
    path('assets/<int:pk>/edit/', views.asset_update, name='asset_update'),

    # Providers
    path('providers/', views.provider_list, name='provider_list'),
    path('providers/create/', views.provider_create, name='provider_create'),
    path('providers/<int:pk>/', views.provider_detail, name='provider_detail'),
    path('providers/<int:pk>/edit/', views.provider_update, name='provider_update'),
]
