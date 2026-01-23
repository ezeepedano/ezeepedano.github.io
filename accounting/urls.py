from django.urls import path
from . import views

urlpatterns = [
    path('ledger/', views.JournalEntryListView.as_view(), name='accounting_ledger'),
    path('trial-balance/', views.TrialBalanceView.as_view(), name='accounting_trial_balance'),
]
