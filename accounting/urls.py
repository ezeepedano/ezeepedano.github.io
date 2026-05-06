from django.urls import path
from . import views

urlpatterns = [
    path('ledger/', views.JournalEntryListView.as_view(), name='accounting_ledger'),
    path('ledger/new/', views.ledger_create, name='accounting_ledger_create'),
    path('ledger/export/', views.ledger_export_csv, name='accounting_ledger_export'),
    path('ledger/<int:pk>/', views.ledger_detail, name='accounting_ledger_detail'),
    path('ledger/<int:pk>/edit/', views.ledger_edit, name='accounting_ledger_edit'),
    path('ledger/<int:pk>/delete/', views.ledger_delete, name='accounting_ledger_delete'),
    path('ledger/<int:pk>/toggle-post/', views.ledger_toggle_post, name='accounting_ledger_toggle_post'),
    path('trial-balance/', views.TrialBalanceView.as_view(), name='accounting_trial_balance'),
]
