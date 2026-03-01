"""
Stock Alerts Management Command

Checks for products and ingredients with low stock levels.
Sends an email alert with a summary table, or prints to console
if email is not configured.

Usage:
    python manage.py check_stock_alerts
"""

import logging
from django.core.management.base import BaseCommand
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone

from inventory.models import Product, Ingredient

logger = logging.getLogger(__name__)

LOW_STOCK_THRESHOLD = 10  # Default for products without min_stock field


class Command(BaseCommand):
    help = 'Verifica stock bajo de productos e ingredientes y envia alerta'

    def handle(self, *args, **options):
        now = timezone.now().strftime('%d/%m/%Y %H:%M')

        # --- Products with low stock ---
        low_products = Product.objects.filter(
            stock_quantity__lt=LOW_STOCK_THRESHOLD
        ).order_by('stock_quantity')

        # --- Ingredients with low stock (stock <= min_stock) ---
        low_ingredients = []
        for ing in Ingredient.objects.all():
            if ing.is_low_stock:
                low_ingredients.append(ing)

        total_alerts = low_products.count() + len(low_ingredients)

        if total_alerts == 0:
            self.stdout.write(self.style.SUCCESS(
                f'[OK] [{now}] Sin alertas de stock. Todo en orden.'
            ))
            return

        # --- Build report ---
        lines = [f'[!] ALERTA DE STOCK BAJO -- {now}', '']

        if low_products.exists():
            lines.append(f'PRODUCTOS ({low_products.count()}):')
            lines.append(f'  {"Producto":<40} {"Stock":>8} {"Minimo":>8}')
            lines.append(f'  {"-"*40} {"-----":>8} {"------":>8}')
            for p in low_products:
                lines.append(
                    f'  {p.name[:40]:<40} {p.stock_quantity:>8} '
                    f'{LOW_STOCK_THRESHOLD:>8}'
                )
            lines.append('')

        if low_ingredients:
            lines.append(f'INGREDIENTES ({len(low_ingredients)}):')
            lines.append(f'  {"Ingrediente":<40} {"Stock":>8} {"Minimo":>8}')
            lines.append(f'  {"-"*40} {"-----":>8} {"------":>8}')
            for ing in low_ingredients:
                lines.append(
                    f'  {ing.name[:40]:<40} {ing.stock_quantity:>8.1f} '
                    f'{ing.min_stock:>8.1f}'
                )
            lines.append('')

        report_text = '\n'.join(lines)

        # --- Build HTML for email ---
        html_rows_products = ''
        for p in low_products:
            color = '#dc3545' if p.stock_quantity <= 0 else '#ffc107'
            html_rows_products += (
                f'<tr>'
                f'<td>{p.sku}</td>'
                f'<td>{p.name}</td>'
                f'<td style="color:{color};font-weight:bold">{p.stock_quantity}</td>'
                f'<td>{LOW_STOCK_THRESHOLD}</td>'
                f'</tr>'
            )

        html_rows_ingredients = ''
        for ing in low_ingredients:
            color = '#dc3545' if ing.stock_quantity <= 0 else '#ffc107'
            html_rows_ingredients += (
                f'<tr>'
                f'<td>{ing.code}</td>'
                f'<td>{ing.name}</td>'
                f'<td style="color:{color};font-weight:bold">{ing.stock_quantity:.1f} {ing.unit}</td>'
                f'<td>{ing.min_stock:.1f} {ing.unit}</td>'
                f'</tr>'
            )

        html_content = f"""
        <h2>Alerta de Stock Bajo -- {now}</h2>
        <p>Se detectaron <strong>{total_alerts}</strong> items con stock bajo.</p>
        """

        if html_rows_products:
            html_content += f"""
            <h3>Productos ({low_products.count()})</h3>
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <tr style="background:#f0f0f0"><th>SKU</th><th>Nombre</th><th>Stock</th><th>Minimo</th></tr>
            {html_rows_products}
            </table>
            """

        if html_rows_ingredients:
            html_content += f"""
            <h3>Ingredientes ({len(low_ingredients)})</h3>
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;">
            <tr style="background:#f0f0f0"><th>Codigo</th><th>Nombre</th><th>Stock</th><th>Minimo</th></tr>
            {html_rows_ingredients}
            </table>
            """

        # --- Print to console ---
        self.stdout.write(self.style.WARNING(report_text))

        # --- Send email if configured ---
        try:
            if hasattr(settings, 'EMAIL_HOST_USER') and settings.EMAIL_HOST_USER:
                send_mail(
                    subject=f'ERP: {total_alerts} alertas de stock bajo',
                    message=report_text,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[settings.EMAIL_HOST_USER],
                    html_message=html_content,
                    fail_silently=False,
                )
                self.stdout.write(self.style.SUCCESS(
                    f'[EMAIL] Enviado a {settings.EMAIL_HOST_USER}'
                ))
            else:
                self.stdout.write(self.style.NOTICE(
                    '[INFO] Email no configurado (EMAIL_HOST_USER). '
                    'Reporte mostrado solo en consola.'
                ))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'[ERROR] Error al enviar email: {e}'))
            logger.error(f'Stock alert email failed: {e}')
