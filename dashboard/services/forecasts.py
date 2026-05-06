"""
Forecasting + auto-target services for the executive dashboard.

This module is intentionally framework-light: every public function takes a
``user`` and returns plain dicts/lists ready to be JSON-encoded by the view
layer.

Design:
    * Sales forecast — simple ordinary-least-squares (OLS) linear regression
      on the rebucketed series produced by ExecutiveMetricsService. Returns
      ``horizon`` future points plus a ±1σ confidence band.
    * Auto-targets — per-period objective derived from the trailing 3-period
      moving average plus the observed period-over-period growth rate. The
      target evolves automatically as new sales come in and historical
      buckets accumulate.
    * Cash forecast — 90-day daily projection: opening balance plus expected
      receivables minus committed payables minus recurring fixed costs.
    * Unified stock alerts — combines low-stock products and at-risk
      ingredients into a single, urgency-sorted feed for the dashboard.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Dict, Any

from django.utils import timezone
from django.db.models import Sum

from sales.models import Sale, SaleItem
from finance.models import CashMovement, Account, FixedCost, Purchase
from inventory.models import Product, Ingredient, Recipe


# ---------------------------------------------------------------------------
# Sales forecast (OLS on bucketed history)
# ---------------------------------------------------------------------------

class SalesForecaster:

    @staticmethod
    def _ols(xs: List[float], ys: List[float]):
        """Returns (slope, intercept, residual_std). Pure-python OLS, no numpy."""
        n = len(xs)
        if n < 2:
            return 0.0, (ys[0] if ys else 0.0), 0.0
        mx = sum(xs) / n
        my = sum(ys) / n
        num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        den = sum((x - mx) ** 2 for x in xs) or 1.0
        slope = num / den
        intercept = my - slope * mx
        # residual std-dev (population)
        resid = [(y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys)]
        sigma = (sum(resid) / n) ** 0.5
        return slope, intercept, sigma

    @staticmethod
    def project(points: List[Dict[str, Any]], horizon: int = 4, bucket: str = 'week') -> List[Dict[str, Any]]:
        """
        Project ``horizon`` future buckets given a list of historical points
        ``[{'start': 'YYYY-MM-DD', 'end': 'YYYY-MM-DD', 'numeric_value': Decimal}, ...]``.

        Returns a list of ``{'start','end','value','low','high','forecast': True}``.
        """
        if not points:
            return []

        ys = [float(p.get('numeric_value', p.get('value', 0)) or 0) for p in points]
        xs = list(range(len(ys)))
        slope, intercept, sigma = SalesForecaster._ols(xs, ys)

        # Step depends on bucket
        if bucket == 'day':
            step = timedelta(days=1)
        elif bucket == 'biweek':
            step = timedelta(days=15)
        elif bucket == 'month':
            step = timedelta(days=30)  # nominal — we anchor to month start below
        else:  # week
            step = timedelta(days=7)

        # Anchor at last bucket end
        try:
            last_end = date.fromisoformat(points[-1]['end'])
        except Exception:
            last_end = timezone.now().date()

        out: List[Dict[str, Any]] = []
        for i in range(1, horizon + 1):
            x_future = len(ys) - 1 + i
            yhat = max(0.0, slope * x_future + intercept)
            band = 1.0 * sigma * (i ** 0.5)  # widening confidence band
            if bucket == 'month':
                # advance to month-after-last by adding 32 days then truncating
                f_start = (last_end + timedelta(days=1)).replace(day=1) if i == 1 else (out[-1]['_end'] + timedelta(days=1)).replace(day=1)
                # last day of that month
                next_month = (f_start.replace(day=28) + timedelta(days=4)).replace(day=1)
                f_end = next_month - timedelta(days=1)
            else:
                f_start = last_end + timedelta(days=1) if i == 1 else out[-1]['_end'] + timedelta(days=1)
                f_end = f_start + step - timedelta(days=1)
            out.append({
                'start': f_start.strftime('%Y-%m-%d'),
                'end':   f_end.strftime('%Y-%m-%d'),
                'value': round(yhat, 2),
                'low':   round(max(0.0, yhat - band), 2),
                'high':  round(yhat + band, 2),
                'forecast': True,
                '_end':  f_end,  # internal cursor — stripped before serialization
            })
        for p in out:
            p.pop('_end', None)
        return out


# ---------------------------------------------------------------------------
# Auto-targets (no human-set goals)
# ---------------------------------------------------------------------------

class TargetEngine:

    @staticmethod
    def from_history(points: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute an auto-target for the *next* period based on the trailing
        3-period moving average and the observed period-over-period growth
        rate. Falls back gracefully when history is short.

        Returns:
            {
              'value': Decimal — target for next period,
              'method': 'ma3+growth' | 'ma3' | 'last' | 'none',
              'baseline': Decimal — moving-avg used as base,
              'growth_pct': float — applied growth (e.g. 4.5 means +4.5%)
            }
        """
        ys = [float(p.get('numeric_value', p.get('value', 0)) or 0) for p in points or []]
        if not ys:
            return {'value': 0, 'method': 'none', 'baseline': 0, 'growth_pct': 0.0}

        if len(ys) >= 4:
            ma3 = sum(ys[-3:]) / 3
            ma3_prev = sum(ys[-6:-3]) / 3 if len(ys) >= 6 else (sum(ys[-4:-1]) / 3)
            growth = ((ma3 - ma3_prev) / ma3_prev) if ma3_prev > 0 else 0
            growth = max(-0.30, min(0.30, growth))  # clamp to ±30% sanity
            target = ma3 * (1 + growth)
            return {
                'value': round(target, 2),
                'method': 'ma3+growth',
                'baseline': round(ma3, 2),
                'growth_pct': round(growth * 100, 1),
            }
        if len(ys) >= 3:
            ma3 = sum(ys[-3:]) / 3
            return {'value': round(ma3, 2), 'method': 'ma3', 'baseline': round(ma3, 2), 'growth_pct': 0.0}
        return {'value': round(ys[-1], 2), 'method': 'last', 'baseline': round(ys[-1], 2), 'growth_pct': 0.0}

    @staticmethod
    def progress(actual: float, target: float) -> Dict[str, Any]:
        """% of target achieved + status color."""
        target = float(target or 0)
        actual = float(actual or 0)
        pct = (actual / target * 100) if target > 0 else 0
        if target <= 0:
            status = 'slate'
        elif pct >= 100:
            status = 'success'
        elif pct >= 80:
            status = 'warning'
        else:
            status = 'danger'
        return {'pct': round(pct, 1), 'status': status}


# ---------------------------------------------------------------------------
# Cash forecast — next 90 days
# ---------------------------------------------------------------------------

class CashForecaster:

    @staticmethod
    def project_90d(user, days: int = 90) -> Dict[str, Any]:
        """
        Build a daily cash projection for the next ``days`` days.

        Inflows:
            * Open receivables — counted on their ``due_date``. If the date
              is past, counted today.
        Outflows:
            * Open payables (Purchases) on ``due_date``.
            * Recurring fixed costs (FixedCost.amount), spread monthly across
              the horizon on each cost's day-of-month.

        Returns:
            {'opening': float, 'points': [{date, balance, inflow, outflow}, ...]}
        """
        today = timezone.now().date()
        horizon_end = today + timedelta(days=days)

        # ── Opening balance ──
        accounts = Account.objects.filter(user=user, is_active=True)
        opening = Decimal('0')
        for acc in accounts:
            in_mo = CashMovement.objects.filter(user=user, account=acc, type='IN').aggregate(s=Sum('amount'))['s'] or Decimal('0')
            out_mo = CashMovement.objects.filter(user=user, account=acc, type='OUT').aggregate(s=Sum('amount'))['s'] or Decimal('0')
            opening += (acc.opening_balance or Decimal('0')) + in_mo - out_mo

        # ── Inflows: open receivables ──
        inflows: Dict[date, Decimal] = {}
        try:
            recv = Sale.objects.filter(user=user, payment_status__in=['PENDING', 'PARTIAL'])
            for s in recv:
                bal = getattr(s, 'balance', None) or Decimal('0')
                if bal <= 0:
                    continue
                due = getattr(s, 'due_date', None) or today
                if due < today:
                    due = today
                if due > horizon_end:
                    continue
                inflows[due] = inflows.get(due, Decimal('0')) + Decimal(bal)
        except Exception:
            pass

        # ── Outflows: open payables ──
        outflows: Dict[date, Decimal] = {}
        try:
            pay = Purchase.objects.filter(user=user, payment_status__in=['PENDING', 'PARTIAL'])
            for p in pay:
                bal = getattr(p, 'balance', None) or Decimal('0')
                if bal <= 0:
                    continue
                due = getattr(p, 'due_date', None) or today
                if due < today:
                    due = today
                if due > horizon_end:
                    continue
                outflows[due] = outflows.get(due, Decimal('0')) + Decimal(bal)
        except Exception:
            pass

        # ── Recurring fixed costs ──
        try:
            for fc in FixedCost.objects.filter(user=user, is_active=True):
                amount = getattr(fc, 'amount', None) or Decimal('0')
                if amount <= 0:
                    continue
                day_of_month = getattr(fc, 'due_day', None) or 10
                cursor = today
                while cursor <= horizon_end:
                    try:
                        candidate = cursor.replace(day=min(day_of_month, 28))
                    except ValueError:
                        candidate = cursor
                    if candidate >= today and candidate <= horizon_end:
                        outflows[candidate] = outflows.get(candidate, Decimal('0')) + Decimal(amount)
                    # advance one month
                    if cursor.month == 12:
                        cursor = cursor.replace(year=cursor.year + 1, month=1, day=1)
                    else:
                        cursor = cursor.replace(month=cursor.month + 1, day=1)
        except Exception:
            pass

        # ── Build daily series ──
        points: List[Dict[str, Any]] = []
        running = opening
        cursor = today
        while cursor <= horizon_end:
            inflow = inflows.get(cursor, Decimal('0'))
            outflow = outflows.get(cursor, Decimal('0'))
            running = running + inflow - outflow
            points.append({
                'date':    cursor.strftime('%Y-%m-%d'),
                'balance': float(running),
                'inflow':  float(inflow),
                'outflow': float(outflow),
            })
            cursor += timedelta(days=1)

        return {
            'opening':  float(opening),
            'minimum':  float(min((Decimal(str(p['balance'])) for p in points), default=opening)),
            'final':    float(running),
            'points':   points,
        }


# ---------------------------------------------------------------------------
# Unified stock alerts — products + ingredients in one feed
# ---------------------------------------------------------------------------

class UnifiedStockAlerts:

    @staticmethod
    def build(user, limit: int = 30) -> List[Dict[str, Any]]:
        """
        Single feed combining:
            - Finished products with low days-of-cover (existing logic).
            - Raw ingredients with short runway (existing intelligence svc).

        Returned list is sorted by urgency (smallest cover first) and tagged:
            kind: 'product' | 'ingredient'
            severity: 'red' (≤7d) | 'amber' (≤21d) | 'green' (>21d)
        """
        alerts: List[Dict[str, Any]] = []

        # Products
        from .executive_metrics import ExecutiveMetricsService
        for a in ExecutiveMetricsService.get_stock_alerts(user):
            cover = a.get('cover', 0)
            severity = 'red' if cover <= 7 else ('amber' if cover <= 21 else 'green')
            p = a.get('product')
            alerts.append({
                'kind':      'product',
                'name':      getattr(p, 'name', '—'),
                'sku':       getattr(p, 'sku', '') or '',
                'stock':     float(a.get('stock', 0) or 0),
                'unit':      'u',
                'velocity':  float(a.get('velocity_30d', 0) or 0),
                'cover':     round(float(cover or 0), 1),
                'severity':  severity,
            })

        # Ingredients
        try:
            from inventory.services_intelligence import StockIntelligenceService
            svc = StockIntelligenceService(user=user, days_history=30)
            for f in svc.get_all_ingredients_forecast():
                runway = f.get('runway_days', 9999)
                if runway >= 9999:
                    continue  # safe — skip
                severity = 'red' if runway <= 7 else ('amber' if runway <= 21 else 'green')
                if severity == 'green':
                    continue
                ing = f.get('ingredient')
                alerts.append({
                    'kind':      'ingredient',
                    'name':      getattr(ing, 'name', '—'),
                    'sku':       getattr(ing, 'sku', '') or '',
                    'stock':     float(getattr(ing, 'stock_quantity', 0) or 0),
                    'unit':      str(getattr(ing, 'unit', '') or ''),
                    'velocity':  float(f.get('daily_usage', 0) or 0),
                    'cover':     round(float(runway or 0), 1),
                    'severity':  severity,
                })
        except Exception:
            pass

        alerts.sort(key=lambda a: (a['severity'] != 'red', a['cover']))
        return alerts[:limit]
