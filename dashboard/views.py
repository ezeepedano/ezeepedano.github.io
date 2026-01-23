from django.shortcuts import render
from django.views.generic import TemplateView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from .services.executive_metrics import ExecutiveMetricsService
from .services.advanced_kpis import AdvancedKPICalculator
from datetime import datetime, date, timedelta
from django.utils import timezone

class ExecutiveDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Pre-load some static data or initial state if needed
        # But mostly we will fetch via AJAX for speed ? 
        # Actually user wants "Home loads fast". AJAX is good for that.
        # But for basics, we can render filters.
        return context

class DashboardBaseJson(LoginRequiredMixin, View):
    def get_filters(self):
        """
        Parse common filters from request.GET
        """
        filters = {'user': self.request.user}
        
        # Date Range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        import datetime
        
        if date_from:
            filters['date__gte'] = date_from
        else:
            # Default to 2026-01-01 for Finance if not specified? 
            # Or handle defaults in frontend?
            # User said: "Finanzas siempre default desde 2026-01-01".
            pass 

        if date_to:
            filters['date__lte'] = date_to
            
        # Channel
        channel = self.request.GET.get('channel')
        if channel and channel != 'ALL':
            filters['channel'] = channel
            
        return filters

class DashboardKPIsView(DashboardBaseJson):
    def get(self, request):
        filters = self.get_filters()
        data = ExecutiveMetricsService.get_kpis(filters)
        return JsonResponse(data)

class DashboardTrendsView(DashboardBaseJson):
    def get(self, request):
        filters = self.get_filters()
        
        bucket = request.GET.get('bucket', 'week')
        try:
            window = int(request.GET.get('window', '12'))
        except:
            window = 12
            
        # If 'window' mode is used (implied by typical usage, but here we support date overrides)
        # If user did NOT explicitly select a custom date range in the frontend for THIS chart override...
        # But wait, existing get_filters parses global date params.
        # If the user wants "Last 12 weeks", we should probably IGNORE the global "2026 YTD" filter?
        # User requirement: "Ventana... Custom (si el usuario elige rango manual)".
        # Typically trend chart has its own controls.
        # If the frontend passes specific bucket/window, we might assume standard mode unless 'date_from' is strictly passed.
        # Let's rely on what get_filters finds.
        # NOTE: If we want strict "Last 12 weeks" regardless of global filter:
        # We need a way to know if date filters are "active" for this chart.
        # Frontend logic: If I select "12 Periods", I should clear date params in the fetch call?
        # Yes, I will implement that in Frontend.
        
        data = ExecutiveMetricsService.get_sales_trends(filters, bucket=bucket, window=window)
        return JsonResponse(data)

class DashboardChannelView(DashboardBaseJson):
    def get(self, request):
        filters = self.get_filters()
        data = ExecutiveMetricsService.get_channel_breakdown(filters)
        return JsonResponse(data, safe=False)

class DashboardFinanceView(LoginRequiredMixin, View):
    def get(self, request):
        # Finance balances are live, mostly no date filter unless historial.
        # User requirement: Live Balance.
        data = ExecutiveMetricsService.get_finance_balances(request.user)
        return JsonResponse(data, safe=False)

class DashboardRecentMovesView(LoginRequiredMixin, View):
    def get(self, request):
        moves = ExecutiveMetricsService.get_recent_movements(request.user)
        data = []
        for m in moves:
            data.append({
                'date': m.date.strftime('%Y-%m-%d'),
                'account': m.account.name,
                'category': m.get_category_display(),
                'type': m.type,
                'amount': m.amount,
                'description': m.description
            })
        return JsonResponse(data, safe=False)
        
class DashboardAgingView(LoginRequiredMixin, View):
    def get(self, request):
        preview = ExecutiveMetricsService.get_aging_preview(request.user)
        # Serialize
        receivables = []
        for s in preview['receivables']:
            receivables.append({
                'id': s.id,
                'entity': s.customer.name if s.customer else 'Unknown',
                'amount': s.balance,
                'due_date': s.due_date,
                'overdue': s.due_date < timezone.now().date() if s.due_date else False
            })
            
        payables = []
        for p in preview['payables']:
             payables.append({
                'id': p.id,
                'entity': p.provider.name if p.provider else 'Unknown',
                'amount': p.balance,  # Use balance property
                'due_date': p.due_date.strftime('%Y-%m-%d') if p.due_date else None,
                'overdue': p.due_date < timezone.now().date() if p.due_date else False
            })
            
        return JsonResponse({'receivables': receivables, 'payables': payables})

class DashboardTopProductsView(DashboardBaseJson):
    def get(self, request):
        filters = self.get_filters()
        data = ExecutiveMetricsService.get_top_products(filters)
        return JsonResponse(data, safe=False)

class DashboardStockAlertsView(LoginRequiredMixin, View):
    def get(self, request):
        alerts = ExecutiveMetricsService.get_stock_alerts(request.user)
        # Serialize
        data = []
        for a in alerts:
            data.append({
                'product_name': a['product'].name,
                'stock': a['stock'],
                'velocity': a['velocity_30d'],
                'cover': a['cover'],
                'status': a['status']
            })
        return JsonResponse(data, safe=False)

class DashboardCustomerView(DashboardBaseJson):
    def get(self, request):
        filters = self.get_filters()
        data = ExecutiveMetricsService.get_customer_metrics(filters)
        return JsonResponse(data, safe=False)

# Nuevas vistas para KPIs avanzados

class DashboardGMROIView(LoginRequiredMixin, View):
    """Vista para GMROI (Gross Margin Return on Investment)"""
    def get(self, request):
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Default al último trimestre
        if not date_from or not date_to:
            date_to = datetime.now().date()
            date_from = date_to - timedelta(days=90)
        
        data = AdvancedKPICalculator.calculate_gmroi(
            user=request.user,
            date_from=date_from,
            date_to=date_to
        )
        return JsonResponse({'products': data}, safe=False)

class DashboardCCCView(LoginRequiredMixin, View):
    """Vista para CCC (Cash Conversion Cycle)"""
    def get(self, request):
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        
        # Default al último trimestre
        if not date_from or not date_to:
            date_to = datetime.now().date()
            date_from = date_to - timedelta(days=90)
        else:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        
        data = AdvancedKPICalculator.calculate_cash_conversion_cycle(
            user=request.user,
            date_from=date_from,
            date_to=date_to
        )
        return JsonResponse(data)

class DashboardCLVView(LoginRequiredMixin, View):
    """Vista para CLV (Customer Lifetime Value)"""
    def get(self, request):
        data = AdvancedKPICalculator.calculate_customer_lifetime_value(
            user=request.user
        )
        return JsonResponse({'customers': data}, safe=False)

class DashboardABCView(LoginRequiredMixin, View):
    """Vista para Análisis ABC de productos"""
    def get(self, request):
        data = AdvancedKPICalculator.calculate_abc_analysis(
            user=request.user
        )
        return JsonResponse(data)

from inventory.services_intelligence import StockIntelligenceService

class BusinessIntelligenceView(LoginRequiredMixin, TemplateView):
    """Vista principal del Dashboard de Inteligencia de Negocios"""
    template_name = 'dashboard/bi.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['today'] = timezone.now().date()
        
        # Add Stock Intelligence Forecasts
        service = StockIntelligenceService(days_history=30)
        context['forecasts'] = service.get_all_ingredients_forecast()
        
        return context
