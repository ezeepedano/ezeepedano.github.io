"""
PDF Report Views for Production module.
Generates 5 types of PDF reports using xhtml2pdf.
"""
import os
import logging
import base64
import qrcode
from io import BytesIO
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import F

from django.http import HttpResponse, Http404
from django.template.loader import get_template
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.conf import settings

from xhtml2pdf import pisa

from production.models import (
    ProductionOrder, BillOfMaterial, BomLine,
    ProductSpecification, QualityResult, CompanyConfig,
)
from traceability.models import (
    IngredientLot, ProductionBatch, BatchConsumption, SaleBatchAllocation,
)
from inventory.models import Product, Ingredient

logger = logging.getLogger(__name__)


# ============================================================================
# UTILITY
# ============================================================================

def render_to_pdf(template_path, context, filename='report.pdf'):
    """Render an HTML template to a PDF HttpResponse."""
    template = get_template(template_path)
    html = template.render(context)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'

    result = BytesIO()
    pdf = pisa.pisaDocument(BytesIO(html.encode('utf-8')), result, encoding='utf-8')

    if pdf.err:
        logger.error("Error generating PDF: %s", pdf.err)
        return HttpResponse('Error al generar el PDF.', status=500)

    response.write(result.getvalue())
    return response


def generate_qr_base64(data):
    """Generate a base64 encoded PNG of a QR code containing the data."""
    if not data:
        return ""
    qr = qrcode.QRCode(version=1, box_size=3, border=1)
    qr.add_data(str(data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode('utf-8')

def _base_context(request, filename):
    """Build common context for all reports."""
    now = date.today()
    config = CompanyConfig.get_config()

    # Try to resolve logo path
    logo_path = None
    if config.logo_image:
        try:
            logo_path = config.logo_image.path
        except Exception:
            pass

    return {
        'print_date': now.strftime('%d/%m/%Y'),
        'print_user': request.user.get_full_name() or request.user.username,
        'filename': filename,
        'logo_path': logo_path,
        'company_name': config.company_name,
    }


# ============================================================================
# REPORT 1: ORDEN DE PRODUCCION (BATCH RECORD)
# ============================================================================

@login_required
def production_order_pdf(request, pk):
    """Generate Production Order (Batch Record) PDF."""
    order = get_object_or_404(
        ProductionOrder.objects.select_related('product', 'bom'), pk=pk, user=request.user
    )

    filename = f"OP_{order.code}.pdf"
    ctx = _base_context(request, filename)

    # Determine lot code
    lot_code = order.code
    batches = order.batches.all()
    if batches.exists():
        lot_code = batches.first().internal_lot_code

    # Calculate expiry date (product shelf_life if available)
    expiry_date = None
    if order.start_date and hasattr(order.product, 'shelf_life_days'):
        shelf_life = getattr(order.product, 'shelf_life_days', None)
        if shelf_life:
            expiry_date = order.start_date + timedelta(days=shelf_life)

    # Build BOM lines with FEFO lot suggestions
    bom_lines = []
    if order.bom:
        for line in order.bom.lines.select_related('ingredient', 'component_product').all():
            if line.ingredient:
                name = line.ingredient.name
                code = getattr(line.ingredient, 'code', '') or line.ingredient.pk
                ing_type = line.ingredient.type

                # FEFO: suggest oldest available lot (not expired)
                suggested_lot = ''
                oldest = IngredientLot.objects.filter(
                    ingredient=line.ingredient,
                    is_active=True,
                    quantity_current__gt=0,
                ).exclude(
                    expiration_date__lt=date.today()
                ).order_by(F('expiration_date').asc(nulls_last=True), 'received_date').first()
                if oldest:
                    suggested_lot = oldest.internal_id

                if ing_type == 'raw_material':
                    # Quantity is % of batch weight; quantity already in grams
                    qty_theoretical = (line.quantity / 100) * order.quantity_to_produce
                    unit = 'g'
                else:
                    # Supply: fixed units
                    qty_theoretical = line.quantity * order.quantity_to_produce
                    unit = line.ingredient.unit or 'u'

            elif line.component_product:
                name = line.component_product.name
                code = line.component_product.sku or line.component_product.pk
                unit = str(getattr(line.component_product, 'unit_measure', 'un'))
                suggested_lot = ''
                qty_theoretical = line.quantity * order.quantity_to_produce
            else:
                continue

            bom_lines.append({
                'code': code,
                'name': name,
                'suggested_lot': suggested_lot,
                'qty_theoretical': f"{int(round(qty_theoretical))}",
                'unit': unit,
            })

    config = CompanyConfig.get_config()
    ctx.update({
        'order': order,
        'lot_code': lot_code,
        'lot_qr_base64': generate_qr_base64(lot_code),
        'expiry_date': expiry_date,
        'bom_lines': bom_lines,
        'dt_name': config.technical_director_name,
    })

    return render_to_pdf('reports/production_order.html', ctx, filename)


# ============================================================================
# REPORT 2: EXPLOSION DE INSUMOS (MRP / PICKING)
# ============================================================================

@login_required
def mrp_explosion_pdf(request, bom_id):
    """Generate MRP Explosion / Picking List PDF."""
    quantity = Decimal(request.GET.get('qty', '1'))
    bom = get_object_or_404(
        BillOfMaterial.objects.prefetch_related('lines__ingredient', 'lines__component_product'),
        pk=bom_id, user=request.user
    )

    # Get the product from BOM
    product = bom.product or (bom.products.first() if bom.products.exists() else None)
    if not product:
        raise Http404("No se encontro producto asociado a esta formula.")

    filename = f"MRP_{bom.code or bom.pk}_{quantity}.pdf"
    ctx = _base_context(request, filename)

    raw_materials = []
    supplies = []
    has_shortage = False
    total_cost_projected = Decimal('0')

    for line in bom.lines.all():
        line_cost = Decimal('0')
        
        if line.ingredient:
            name = line.ingredient.name
            code = getattr(line.ingredient, 'code', '') or str(line.ingredient.pk)
            ing_type = line.ingredient.type
            unit_cost = line.ingredient.cost_per_unit or Decimal('0')

            if ing_type == 'raw_material':
                # Quantity stored as % of batch weight (e.g. 7 = 7%)
                # quantity is already in grams
                required = (line.quantity / 100) * quantity
                unit = 'g'
                stock = line.ingredient.stock_quantity * 1000  # kg -> g
                line_cost = (Decimal(required) / 1000) * unit_cost
            else:
                # Supply/packaging: fixed units per batch-unit produced
                required = line.quantity * quantity
                unit = line.ingredient.unit or 'u'
                stock = line.ingredient.stock_quantity
                line_cost = Decimal(required) * unit_cost

        elif line.component_product:
            name = line.component_product.name
            code = line.component_product.sku or str(line.component_product.pk)
            unit = str(getattr(line.component_product, 'unit_measure', 'un'))
            required = line.quantity * quantity
            stock = line.component_product.stock_quantity
            # Assuming product has a base cost or zero for this scope
            line_cost = Decimal('0')
        else:
            continue

        difference = stock - required
        shortage = difference < 0

        if shortage:
            has_shortage = True
            
        total_cost_projected += line_cost

        item_data = {
            'code': code,
            'name': name,
            'required': f"{int(round(required))}",
            'stock': f"{int(round(stock))}",
            'difference': f"{int(round(difference))}",
            'unit': unit,
            'shortage': shortage,
            'cost': line_cost,
        }
        
        if line.ingredient and line.ingredient.type == 'supply':
            supplies.append(item_data)
        else:
            raw_materials.append(item_data)

    ctx.update({
        'product': product,
        'bom': bom,
        'quantity': quantity,
        'raw_materials': raw_materials,
        'supplies': supplies,
        'total_cost': total_cost_projected,
        'has_shortage': has_shortage,
    })

    return render_to_pdf('reports/mrp_explosion.html', ctx, filename)


# ============================================================================
# REPORT 3A: TRAZABILIDAD INVERSA (Backward)
# ============================================================================

@login_required
def traceability_backward_pdf(request, batch_id):
    """Backward traceability: from finished product lot -> raw materials used."""
    batch = get_object_or_404(
        ProductionBatch.objects.select_related('product'), pk=batch_id, user=request.user
    )

    consumptions = BatchConsumption.objects.filter(
        production_batch=batch,
        is_waste=False,
    ).select_related('ingredient', 'ingredient_lot').order_by('ingredient__name')

    filename = f"TRAZ_{batch.internal_lot_code}.pdf"
    ctx = _base_context(request, filename)
    ctx.update({
        'mode': 'backward',
        'batch': batch,
        'consumptions': consumptions,
    })

    return render_to_pdf('reports/traceability.html', ctx, filename)


# ============================================================================
# REPORT 3B: TRAZABILIDAD DIRECTA (Forward)
# ============================================================================

@login_required
def traceability_forward_pdf(request, lot_id):
    """Forward traceability: from raw material lot -> products and sales."""
    lot = get_object_or_404(
        IngredientLot.objects.select_related('ingredient'), pk=lot_id, user=request.user
    )

    # Find all productions that consumed this lot
    consumptions = BatchConsumption.objects.filter(
        ingredient_lot=lot,
        is_waste=False,
    ).select_related(
        'production_batch__product',
    ).order_by('production_batch__production_date')

    # Find sales linked to those batches
    batch_ids = consumptions.values_list('production_batch_id', flat=True).distinct()
    sales_allocations = SaleBatchAllocation.objects.filter(
        production_batch_id__in=batch_ids
    ).select_related(
        'sale_item__sale', 'production_batch'
    ).order_by('allocation_date')

    filename = f"TRAZ_FWD_{lot.internal_id}.pdf"
    ctx = _base_context(request, filename)
    ctx.update({
        'mode': 'forward',
        'ingredient': lot.ingredient,
        'lot': lot,
        'consumptions': consumptions,
        'sales_allocations': sales_allocations,
    })

    return render_to_pdf('reports/traceability.html', ctx, filename)


# ============================================================================
# REPORT 4: CERTIFICADO DE ANALISIS (CoA)
# ============================================================================

@login_required
def coa_pdf(request, batch_id):
    """Generate Certificate of Analysis PDF for a production batch."""
    batch = get_object_or_404(
        ProductionBatch.objects.select_related('product'), pk=batch_id, user=request.user
    )

    config = CompanyConfig.get_config()

    # Get specifications for this product
    specs = ProductSpecification.objects.filter(
        product=batch.product
    ).order_by('sort_order')

    # Get actual results for this batch (if any)
    existing_results = {
        r.specification_id: r
        for r in QualityResult.objects.filter(production_batch=batch)
    }

    results = []
    for spec in specs:
        result = existing_results.get(spec.pk)
        results.append({
            'parameter': spec.parameter,
            'specification': spec.specification,
            'result': result.result_value if result else spec.specification,
            'method': spec.method,
            'approved': result.approved if result else True,
        })

    # Signature path
    signature_path = None
    if config.signature_image:
        try:
            signature_path = config.signature_image.path
        except Exception:
            pass
            
    # Calculate Automatic Verdict
    all_approved = all(r['approved'] for r in results) if results else False
    verdict = "APROBADO" if all_approved and results else "RECHAZADO"
    
    # Generate Validation QR
    qr_data = f"CoA-{batch.internal_lot_code}-{verdict}"
    validator_qr = generate_qr_base64(qr_data)

    filename = f"CoA_{batch.internal_lot_code}.pdf"
    ctx = _base_context(request, filename)
    ctx.update({
        'batch': batch,
        'results': results,
        'verdict': verdict,
        'validator_qr': validator_qr,
        'dt_name': config.technical_director_name,
        'signature_path': signature_path,
    })

    return render_to_pdf('reports/coa.html', ctx, filename)


# ============================================================================
# REPORT 5: VENCIMIENTOS VALORIZADOS (FEFO)
# ============================================================================

@login_required
def fefo_expiry_pdf(request):
    """Generate FEFO Expiry Valuation report PDF."""
    days = int(request.GET.get('days', 30))
    today = date.today()
    until_date = today + timedelta(days=days)

    # Get ingredient lots near expiry (including already expired)
    lots = IngredientLot.objects.filter(
        is_active=True,
        quantity_current__gt=0,
        expiration_date__isnull=False,
        expiration_date__lte=until_date,
    ).select_related('ingredient').order_by('expiration_date')

    items = []
    total_value = Decimal('0')
    items_expired = 0
    
    # Risk Categories (Values)
    expired_value = Decimal('0')
    high_risk_value = Decimal('0') # 0-14 days
    medium_risk_value = Decimal('0') # > 14 days

    for lot in lots:
        days_remaining = (lot.expiration_date - today).days
        cost_per_unit = lot.ingredient.cost_per_unit or Decimal('0')
        value = lot.quantity_current * cost_per_unit
        
        total_value += value

        if days_remaining < 0:
            items_expired += 1
            expired_value += value
            risk_level = "VENCIDO"
        elif days_remaining <= 14:
            high_risk_value += value
            risk_level = "RIESGO ALTO"
        else:
            medium_risk_value += value
            risk_level = "RIESGO MEDIO"


        items.append({
            'name': lot.ingredient.name,
            'lot_code': f"{lot.internal_id} ({lot.supplier_lot})",
            'expiry_date': lot.expiration_date,
            'days_remaining': days_remaining,
            'stock': f"{lot.quantity_current:.3f}",
            'unit': 'kg',
            'value': value,
            'risk_level': risk_level,
        })

    filename = f"FEFO_{days}d_{today.strftime('%Y%m%d')}.pdf"
    ctx = _base_context(request, filename)
    ctx.update({
        'days': days,
        'until_date': until_date,
        'items': items,
        'total_value': total_value,
        'items_expired': items_expired,
        'expired_value': expired_value,
        'high_risk_value': high_risk_value,
        'medium_risk_value': medium_risk_value,
        'pct_high_risk': (high_risk_value / total_value * 100) if total_value else 0,
        'pct_expired': (expired_value / total_value * 100) if total_value else 0,
    })

    return render_to_pdf('reports/fefo_expiry.html', ctx, filename)


# ============================================================================
# REPORT 6: KARDEX DE INVENTARIO (INVENTORY LEDGER)
# ============================================================================

@login_required
def kardex_pdf(request, ingredient_id):
    """Generate Inventory Ledger (Kardex) PDF for a specific ingredient."""
    ingredient = get_object_or_404(
        Ingredient, pk=ingredient_id, user=request.user
    )
    
    # Get Date Range from Request (Optional, default to last 30 days)
    days = int(request.GET.get('days', 30))
    end_date = date.today()
    start_date = end_date - timedelta(days=days)

    # 1. Get all Lots received in this period (ENTRIES)
    lots_received = IngredientLot.objects.filter(
        ingredient=ingredient,
        received_date__gte=start_date,
        received_date__lte=end_date,
        is_active=True
    ).order_by('received_date')

    # 2. Get all consumptions in this period (EXITS)
    consumptions = BatchConsumption.objects.filter(
        ingredient_lot__ingredient=ingredient,
        production_batch__production_date__gte=start_date,
        production_batch__production_date__lte=end_date
    ).select_related('production_batch', 'ingredient_lot').order_by('production_batch__production_date')

    # Build chronological ledger
    transactions = []
    
    for lot in lots_received:
        transactions.append({
            'date': lot.received_date,
            'type': 'ENTRADA',
            'reference': f"Compra - Lote Prov: {lot.supplier_lot or '-'}",
            'lot_id': lot.internal_id,
            'quantity_in': lot.quantity_initial,
            'quantity_out': 0,
            'balance': 0 # Calculated later
        })
        
    for c in consumptions:
        transactions.append({
            'date': c.production_batch.production_date,
            'type': 'MERMA' if c.is_waste else 'CONSUMO',
            'reference': f"OP: {c.production_batch.internal_lot_code}",
            'lot_id': c.ingredient_lot.internal_id,
            'quantity_in': 0,
            'quantity_out': c.quantity_used,
            'balance': 0
        })
        
    # Sort chronologically
    transactions.sort(key=lambda x: x['date'])

    filename = f"KARDEX_{ingredient.name}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    ctx = _base_context(request, filename)
    ctx.update({
        'ingredient': ingredient,
        'start_date': start_date,
        'end_date': end_date,
        'transactions': transactions,
        'current_stock': ingredient.stock_quantity,
        'unit': ingredient.unit or 'kg'
    })

    return render_to_pdf('reports/kardex.html', ctx, filename)


# ============================================================================
# REPORT 7: ANALISIS DE RENDIMIENTO (BATCH YIELD & COST)
# ============================================================================

@login_required
def batch_yield_pdf(request, batch_id):
    """Generate Yield and Cost Analysis PDF for a completed batch."""
    batch = get_object_or_404(
        ProductionBatch.objects.select_related('product', 'bom'), 
        pk=batch_id, 
        user=request.user
    )
    
    if batch.status != 'COMPLETED':
        return HttpResponse("El analisis de rendimiento solo esta disponible para lotes completados.", status=400)

    # 1. Theoretical Cost (from BOM)
    theoretical_lines = []
    total_theoretical_cost = Decimal('0')
    
    if batch.bom:
        for line in batch.bom.lines.select_related('ingredient').all():
            if line.ingredient:
                unit_cost = line.ingredient.cost_per_unit or Decimal('0')
                if line.ingredient.type == 'raw_material':
                    required = (line.quantity / 100) * batch.quantity_produced
                    line_cost = (Decimal(required) / 1000) * unit_cost
                else:
                    required = line.quantity * batch.quantity_produced
                    line_cost = Decimal(required) * unit_cost
                    
                total_theoretical_cost += line_cost
                theoretical_lines.append({
                    'name': line.ingredient.name,
                    'qty': required,
                    'cost': line_cost
                })

    # 2. Actual Cost (from Consumptions)
    actual_lines = []
    total_actual_cost = Decimal('0')
    consumptions = BatchConsumption.objects.filter(
        production_batch=batch, 
        is_waste=False
    ).select_related('ingredient_lot__ingredient')
    
    for c in consumptions:
        ing = c.ingredient_lot.ingredient
        unit_cost = ing.cost_per_unit or Decimal('0')
        if ing.type == 'raw_material':
             line_cost = (Decimal(c.quantity_used) / 1000) * unit_cost
        else:
             line_cost = Decimal(c.quantity_used) * unit_cost
             
        total_actual_cost += line_cost
        actual_lines.append({
            'name': ing.name,
            'qty': c.quantity_used,
            'cost': line_cost,
            'lot': c.ingredient_lot.internal_id
        })
        
    # Variances
    cost_variance = total_actual_cost - total_theoretical_cost
    variance_pct = (cost_variance / total_theoretical_cost * 100) if total_theoretical_cost else Decimal('0')
    
    unit_cost_actual = (total_actual_cost / Decimal(batch.quantity_produced)) if batch.quantity_produced else Decimal('0')

    filename = f"RENDIMIENTO_{batch.internal_lot_code}.pdf"
    ctx = _base_context(request, filename)
    ctx.update({
        'batch': batch,
        'theoretical_cost': total_theoretical_cost,
        'actual_cost': total_actual_cost,
        'cost_variance': cost_variance,
        'variance_pct': variance_pct,
        'unit_cost_actual': unit_cost_actual,
        'actual_lines': actual_lines,
    })

    return render_to_pdf('reports/batch_yield.html', ctx, filename)


# ============================================================================
# REPORTS HUB (Landing page with all 7 reports)
# ============================================================================

@login_required
def reports_hub(request):
    """Landing page for all PDF reports. All data scoped to request.user."""
    orders = ProductionOrder.objects.filter(
        user=request.user
    ).select_related('product').order_by('-created_at')[:50]
    boms = BillOfMaterial.objects.filter(
        is_active=True, user=request.user
    ).order_by('name')
    batches = ProductionBatch.objects.filter(
        user=request.user
    ).select_related('product').order_by('-production_date')[:50]
    ingredient_lots = IngredientLot.objects.filter(
        is_active=True, quantity_current__gt=0, user=request.user
    ).select_related('ingredient').order_by('-received_date')[:100]

    ingredients = Ingredient.objects.filter(
        user=request.user
    ).order_by('name')
    
    completed_batches = ProductionBatch.objects.filter(
        user=request.user, status='COMPLETED'
    ).select_related('product').order_by('-production_date')[:50]

    return render(request, 'reports/reports_hub.html', {
        'orders': orders,
        'boms': boms,
        'batches': batches,
        'ingredient_lots': ingredient_lots,
        'ingredients': ingredients,
        'completed_batches': completed_batches,
    })
