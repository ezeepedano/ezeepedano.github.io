"""
Daily Report Management Command

Generates and sends a daily summary of sales, revenue,
cash movements, and stock alerts from the previous day.

Usage:
    python manage.py daily_report
    python manage.py daily_report --date 2026-02-17
"""

import logging
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Sum, Count

from sales.models import Sale
from finance.models import CashMovement
from inventory.models import Product, Ingredient

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 10


class Command(BaseCommand):
    help = 'Genera y envia un reporte diario de ventas, caja y stock'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date', type=str, default=None,
            help='Fecha del reporte (YYYY-MM-DD). Default: ayer.'
        )

    def handle(self, *args, **options):
        # Determine report date
        if options['date']:
            report_date = date.fromisoformat(options['date'])
        else:
            report_date = date.today() - timedelta(days=1)

        date_str = report_date.strftime('%d/%m/%Y')
        self.stdout.write(f'\n--- REPORTE DIARIO -- {date_str} ---\n{"="*50}')

        # =====================================================================
        # 1. SALES SUMMARY
        # =====================================================================
        sales_qs = Sale.objects.filter(date__date=report_date)
        sales_agg = sales_qs.aggregate(
            count=Count('id'),
            total_revenue=Sum('total'),
            total_collected=Sum('paid_amount'),
        )

        num_sales = sales_agg['count'] or 0
        revenue = sales_agg['total_revenue'] or Decimal('0')
        collected = sales_agg['total_collected'] or Decimal('0')
        pending = revenue - collected

        # Channel breakdown
        channel_data = (
            sales_qs.values('channel')
            .annotate(count=Count('id'), total=Sum('total'))
            .order_by('-total')
        )

        # =====================================================================
        # 2. CASH MOVEMENTS SUMMARY
        # =====================================================================
        cash_qs = CashMovement.objects.filter(date__date=report_date)

        inflows = cash_qs.filter(type='IN').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        outflows = cash_qs.filter(type='OUT').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        net_cash = inflows - outflows

        # =====================================================================
        # 3. STOCK ALERTS
        # =====================================================================
        low_products = Product.objects.filter(
            stock_quantity__lt=LOW_STOCK_THRESHOLD
        ).count()

        low_ingredients = sum(
            1 for ing in Ingredient.objects.all() if ing.is_low_stock
        )

        # =====================================================================
        # BUILD TEXT REPORT
        # =====================================================================
        lines = [
            f'--- REPORTE DIARIO -- {date_str} ---',
            f'{"="*50}',
            '',
            'VENTAS',
            f'  Cantidad de ventas:  {num_sales}',
            f'  Facturado:           ${revenue:,.2f}',
            f'  Cobrado:             ${collected:,.2f}',
            f'  Pendiente de cobro:  ${pending:,.2f}',
        ]

        if channel_data:
            lines.append('')
            lines.append('  Por canal:')
            for ch in channel_data:
                ch_name = ch['channel'] or 'Sin canal'
                lines.append(
                    f'    - {ch_name}: {ch["count"]} ventas -- ${ch["total"]:,.2f}'
                )

        lines.extend([
            '',
            'MOVIMIENTOS DE CAJA',
            f'  Ingresos:   ${inflows:,.2f}',
            f'  Egresos:    ${outflows:,.2f}',
            f'  Neto:       ${net_cash:,.2f}',
            '',
            'STOCK',
            f'  Productos con stock bajo:     {low_products}',
            f'  Ingredientes con stock bajo:  {low_ingredients}',
        ])

        report_text = '\n'.join(lines)

        # =====================================================================
        # BUILD HTML REPORT
        # =====================================================================
        channel_rows = ''
        for ch in channel_data:
            ch_name = ch['channel'] or 'Sin canal'
            channel_rows += (
                f'<tr><td>{ch_name}</td>'
                f'<td>{ch["count"]}</td>'
                f'<td style="text-align:right">${ch["total"]:,.2f}</td></tr>'
            )

        net_color = '#28a745' if net_cash >= 0 else '#dc3545'
        pending_color = '#dc3545' if pending > 0 else '#28a745'

        html_content = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
        <h2>Reporte Diario -- {date_str}</h2>

        <h3>Ventas</h3>
        <table border="0" cellpadding="4">
        <tr><td>Cantidad de ventas:</td><td><strong>{num_sales}</strong></td></tr>
        <tr><td>Facturado:</td><td><strong>${revenue:,.2f}</strong></td></tr>
        <tr><td>Cobrado:</td><td><strong>${collected:,.2f}</strong></td></tr>
        <tr><td>Pendiente:</td><td style="color:{pending_color}"><strong>${pending:,.2f}</strong></td></tr>
        </table>
        """

        if channel_rows:
            html_content += f"""
            <h4>Por Canal</h4>
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <tr style="background:#f0f0f0"><th>Canal</th><th>Ventas</th><th>Total</th></tr>
            {channel_rows}
            </table>
            """

        html_content += f"""
        <h3>Movimientos de Caja</h3>
        <table border="0" cellpadding="4">
        <tr><td>Ingresos:</td><td style="color:#28a745"><strong>${inflows:,.2f}</strong></td></tr>
        <tr><td>Egresos:</td><td style="color:#dc3545"><strong>${outflows:,.2f}</strong></td></tr>
        <tr><td>Neto:</td><td style="color:{net_color}"><strong>${net_cash:,.2f}</strong></td></tr>
        </table>

        <h3>Stock</h3>
        <table border="0" cellpadding="4">
        <tr><td>Productos con stock bajo:</td><td><strong>{low_products}</strong></td></tr>
        <tr><td>Ingredientes con stock bajo:</td><td><strong>{low_ingredients}</strong></td></tr>
        </table>

        <hr>
        <p style="color:#888;font-size:12px;">Reporte generado automaticamente por Propel ERP</p>
        </div>
        """

        # --- Print to console ---
        self.stdout.write(report_text)
        self.stdout.write('')

        # --- Send email if configured ---
        try:
            if hasattr(settings, 'EMAIL_HOST_USER') and settings.EMAIL_HOST_USER:
                send_mail(
                    subject=f'ERP Reporte Diario -- {date_str}',
                    message=report_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.EMAIL_HOST_USER],
                    html_message=html_content,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'[EMAIL] Reporte enviado a {settings.EMAIL_HOST_USER}'
                ))
            else:
                self.stdout.write(self.style.NOTICE(
                    '[INFO] Email no configurado. Reporte mostrado solo en consola.'
                ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'[ERROR] Error al enviar email: {e}'))
            logger.error(f'Daily report email failed: {e}')
