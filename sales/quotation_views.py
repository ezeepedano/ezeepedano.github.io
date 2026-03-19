"""
Views for the Quotation / Presupuesto module.
"""
import os
import logging
from datetime import date, timedelta
from decimal import Decimal

from django.http import HttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from django.conf import settings

from core_erp.pdf_utils import render_to_pdf

from .models import Quotation, QuotationItem, Customer
from .quotation_forms import QuotationForm, QuotationItemFormSet
from inventory.models import Product
from production.models import CompanyConfig

logger = logging.getLogger(__name__)


# ============================================================================
# CRUD VIEWS
# ============================================================================

@login_required
def quotation_list(request):
    """List all quotations for the current user."""
    quotations = Quotation.objects.filter(
        user=request.user
    ).select_related('customer').order_by('-date', '-pk')

    # Filter by status
    status_filter = request.GET.get('status', '')
    if status_filter:
        quotations = quotations.filter(status=status_filter)

    return render(request, 'sales/quotation_list.html', {
        'quotations': quotations,
        'status_filter': status_filter,
    })


@login_required
def quotation_create(request):
    """Create a new quotation."""
    if request.method == 'POST':
        form = QuotationForm(request.POST, user=request.user)
        formset = QuotationItemFormSet(request.POST, prefix='items')
        if form.is_valid() and formset.is_valid():
            quotation = form.save(commit=False)
            quotation.user = request.user
            quotation.save()
            formset.instance = quotation
            # Set user for product queryset on each form
            for f in formset.forms:
                f.fields['product'].queryset = Product.objects.filter(user=request.user)
            formset.save()
            messages.success(request, f'Presupuesto {quotation.number} creado exitosamente.')
            return redirect('quotation_list')
    else:
        initial = {
            'date': date.today(),
            'valid_until': date.today() + timedelta(days=15),
        }
        form = QuotationForm(initial=initial, user=request.user)
        formset = QuotationItemFormSet(prefix='items')
        # Set product queryset for each form in formset
        for f in formset.forms:
            f.fields['product'].queryset = Product.objects.filter(user=request.user)

    return render(request, 'sales/quotation_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Nuevo Presupuesto',
        'products_json': _get_products_json(request.user),
    })


@login_required
def quotation_edit(request, pk):
    """Edit an existing quotation."""
    quotation = get_object_or_404(Quotation, pk=pk, user=request.user)

    if request.method == 'POST':
        form = QuotationForm(request.POST, instance=quotation, user=request.user)
        formset = QuotationItemFormSet(request.POST, instance=quotation, prefix='items')
        # Set product queryset
        for f in formset.forms:
            f.fields['product'].queryset = Product.objects.filter(user=request.user)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, f'Presupuesto {quotation.number} actualizado.')
            return redirect('quotation_list')
    else:
        form = QuotationForm(instance=quotation, user=request.user)
        formset = QuotationItemFormSet(instance=quotation, prefix='items')
        for f in formset.forms:
            f.fields['product'].queryset = Product.objects.filter(user=request.user)

    return render(request, 'sales/quotation_form.html', {
        'form': form,
        'formset': formset,
        'quotation': quotation,
        'title': f'Editar Presupuesto {quotation.number}',
        'products_json': _get_products_json(request.user),
    })


@login_required
def quotation_delete(request, pk):
    """Delete a quotation."""
    quotation = get_object_or_404(Quotation, pk=pk, user=request.user)
    if request.method == 'POST':
        number = quotation.number
        quotation.delete()
        messages.success(request, f'Presupuesto {number} eliminado.')
        return redirect('quotation_list')
    return render(request, 'sales/quotation_confirm_delete.html', {
        'quotation': quotation,
    })


@login_required
def quotation_duplicate(request, pk):
    """Duplicate an existing quotation."""
    original = get_object_or_404(Quotation, pk=pk, user=request.user)
    items = list(original.items.all())

    # Create new quotation (number auto-generated)
    original.pk = None
    original.number = ''
    original.date = date.today()
    original.valid_until = date.today() + timedelta(days=15)
    original.status = 'DRAFT'
    original.save()

    for item in items:
        item.pk = None
        item.quotation = original
        item.save()

    messages.success(request, f'Presupuesto duplicado como {original.number}.')
    return redirect('quotation_edit', pk=original.pk)


# ============================================================================
# PDF GENERATION
# ============================================================================

@login_required
def quotation_pdf(request, pk):
    """Generate PDF for a quotation."""
    quotation = get_object_or_404(
        Quotation.objects.select_related('customer').prefetch_related('items__product'),
        pk=pk, user=request.user
    )
    config = CompanyConfig.get_config()

    # Logo (prioritize uploaded company config logo, fallback to static)
    logo_path = None
    if config.logo_image and hasattr(config.logo_image, 'path') and os.path.exists(config.logo_image.path):
        logo_path = config.logo_image.path
    else:
        # Fallback to static logos
        static_logo = os.path.join(settings.BASE_DIR, 'static', 'img', 'logos', 'logo_main.png')
        if not os.path.exists(static_logo):
            static_logo = os.path.join(settings.BASE_DIR, 'static', 'img', 'logos', 'logo_report.png')
        if os.path.exists(static_logo):
            logo_path = static_logo

    # Build items with computed values
    items_data = []
    for item in quotation.items.all():
        items_data.append({
            'sku': item.product.sku if item.product else '-',
            'description': item.description,
            'quantity': item.quantity,
            'unit_price': item.unit_price,
            'iva_pct': item.iva_pct,
            'discount_pct': item.discount_pct,
            'line_total': item.line_total,
        })

    filename = f"Presupuesto_{quotation.number}.pdf"
    ctx = {
        'quotation': quotation,
        'items': items_data,
        'customer': quotation.customer,
        'subtotal': quotation.subtotal,
        'discount_amount': quotation.discount_amount,
        'net_gravado': quotation.net_gravado,
        'tax_amount': quotation.tax_amount,
        'total': quotation.total,
        'config': config,
        'company_name': config.company_name,
        'logo_path': logo_path,
        'print_date': date.today().strftime('%d/%m/%Y'),
        'print_user': request.user.get_full_name() or request.user.username,
        'filename': filename,
    }

    return render_to_pdf('reports/quotation_pdf.html', ctx, filename)


# ============================================================================
# API HELPERS
# ============================================================================

def _get_products_json(user):
    """Return a JSON-serializable list of products for JS autocompletion."""
    import json
    products = Product.objects.filter(user=user).order_by('name').values(
        'pk', 'sku', 'name', 'sale_price'
    )
    return json.dumps(list(products), default=str)


@login_required
def product_price_api_quotation(request, pk):
    """Return product details for quotation autocompletion."""
    product = get_object_or_404(Product, pk=pk, user=request.user)
    return JsonResponse({
        'sku': product.sku,
        'name': product.name,
        'sale_price': str(product.sale_price),
    })


# ============================================================================
# COMPANY CONFIG
# ============================================================================

@login_required
def company_config(request):
    """Edit company configuration (name, CUIT, contact, logos)."""
    config = CompanyConfig.get_config()

    if request.method == 'POST':
        # Text fields
        for field in ('company_name', 'company_cuit', 'company_iva_condition',
                      'company_address', 'company_phone', 'company_email',
                      'company_website', 'company_social', 'technical_director_name'):
            setattr(config, field, request.POST.get(field, ''))

        # File fields
        if 'logo_image' in request.FILES:
            config.logo_image = request.FILES['logo_image']
        if 'signature_image' in request.FILES:
            config.signature_image = request.FILES['signature_image']

        config.save()
        messages.success(request, 'Configuración de empresa guardada correctamente.')
        return redirect('company_config')

    return render(request, 'sales/company_config.html', {'config': config})
