"""
Servicios de lógica de negocio para el módulo de trazabilidad.
Implementa FIFO, merma automática, alertas y trazabilidad completa.
"""

from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Sum, Q
from django.core.exceptions import ValidationError

from .models import (
    IngredientLot, 
    ProductionBatch, 
    BatchConsumption, 
    StockAlert,
    TraceabilityConfig
)
from inventory.models import Ingredient, Product
from production.models import BillOfMaterial, BomLine
from finance.models import Purchase, Provider, PurchaseCategory


class StockService:
    """Servicio para gestión de stock e ingreso de compras."""
    
    @staticmethod
    def get_next_internal_id(ingredient):
        """
        Genera el siguiente ID interno para un ingrediente.
        Formato: MP-{CODIGO}-{NUMERO}
        """

        # Get ingredient code
        code = ingredient.code.upper() if ingredient.code else ingredient.name[:3].upper()
        prefix = f"MP-{code}-"
        
        # Find the highest number used with this prefix across ALL ingredients
        # This prevents collisions between "Magnesium" and "Magnolia" (both MAG)
        last_lot = IngredientLot.objects.filter(
            internal_id__startswith=prefix
        ).order_by('-internal_id').first()
        
        if last_lot and last_lot.internal_id:
            try:
                # Extract number from last ID (MP-XYZ-001 -> 001)
                last_num = int(last_lot.internal_id.split('-')[-1])
                next_num = last_num + 1
            except (ValueError, IndexError):
                next_num = 1
        else:
            next_num = 1
        
        return f"{prefix}{next_num:03d}"
    
    @staticmethod
    @transaction.atomic
    def register_purchase(ingredient, quantity, supplier_lot, received_date, 
                         expiration_date=None, cost_per_kg=None, notes=None, user=None,
                         provider=None, category=None, payment_status='PENDING', due_date=None):
        """
        Registra una compra de ingrediente.
        Crea un nuevo IngredientLot con ID interno automático.
        """
        # Generate internal ID
        internal_id = StockService.get_next_internal_id(ingredient)
        
        # Create lot
        lot = IngredientLot.objects.create(
            ingredient=ingredient,
            internal_id=internal_id,
            supplier_lot=supplier_lot,
            quantity_initial=quantity,
            quantity_current=quantity,
            received_date=received_date,
            expiration_date=expiration_date,
            user=user
        )
        
        # Check for alerts
        AlertService.check_new_lot_alerts(lot)
        
        
        
        # Check for alerts
        AlertService.check_new_lot_alerts(lot)
        
        # --- FINANCE INTEGRATION ---
        # Create corresponding Finance Purchase record if cost is provided
        if cost_per_kg and cost_per_kg > 0:
            total_amount = Decimal(str(quantity)) * Decimal(str(cost_per_kg))
            
            # Ensure provider logic (if string name passed or object)
            # Service expects objects usually, but let's handle safety
            
            Purchase.objects.create(
                user=user,
                date=received_date,
                provider=provider,
                category=category,
                code=supplier_lot, # Use supplier lot as invoice code/ref
                description=f"Compra de {ingredient.name} ({quantity} kg) - Lote: {internal_id}",
                amount=total_amount,
                due_date=due_date if due_date else received_date, # Default due date to today if not active
                payment_status=payment_status,
                is_paid=(payment_status == 'PAID')
            )
        
        return lot

    @staticmethod
    def check_and_create_alerts(user):
        """
        Verifica y crea alertas para todos los lotes activos del usuario.
        wrapper para AlertService.check_all_alerts()
        """
        AlertService.check_all_alerts(user)

    @staticmethod
    def get_stock_summary(user):
        """
        Obtiene resumen de stock para la vista del usuario.
        Returns:
            dict con 'ingredients' y 'alerts'
        """
        ingredients_data = []
        ingredients = Ingredient.objects.filter(user=user).prefetch_related('lots').all()
        
        for ingredient in ingredients:
            lots = ingredient.lots.filter(is_active=True).order_by('expiration_date')
            ingredients_data.append({
                'ingredient': ingredient,
                'total_stock': ingredient.stock_quantity,
                'lots': lots
            })
            
        alerts = StockAlert.objects.filter(
            Q(ingredient__user=user) | Q(ingredient_lot__user=user),
            is_resolved=False
        ).order_by('-created_at').distinct()
            
        return {
            'ingredients': ingredients_data,
            'alerts': alerts
        }


class ProductionService:
    """Servicio para registro de producción y consumo de ingredientes."""
    
    @staticmethod
    def check_stock_availability(bom, quantity_produced):
        """
        Verifica si hay stock suficiente para una producción.
        Simula consumo FIFO sin modificar la BD.
        
        Returns:
            dict con 'available': bool y 'details': list
        """
        config = TraceabilityConfig.get_config()
        results = []
        all_available = True
        
        for bom_line in bom.lines.all():
            ingredient = bom_line.ingredient
            if not ingredient:
                continue
            
            # Calculate needed quantity based on ingredient type
            if ingredient.type == 'supply':
                # Supplies are UNITS (e.g. 1 spoon per product)
                # bom_line.quantity = number of units per product
                quantity_needed = Decimal(str(quantity_produced)) * bom_line.quantity
                # No unit conversion for supplies
            else:
                # Raw Materials are PERCENTAGES of the BOM base quantity
                # bom_line.quantity = percentage (e.g. 30 for 30%)
                # Convert to actual kg needed
                percentage = bom_line.quantity
                bom_base_kg = bom.quantity if bom.quantity else Decimal('0.1')
                quantity_per_unit_kg = (percentage / 100) * bom_base_kg
                
                # For different product sizes (e.g. 100g vs 200g)
                # We need to scale by the product weight if applicable
                # But quantity_produced already represents the total batch weight
                # So we use it directly
                quantity_needed = Decimal(str(quantity_produced)) * quantity_per_unit_kg / bom_base_kg
            
            # Apply waste logic (only for raw materials, not supplies)
            if ingredient.type != 'supply' and config.waste_threshold_kg > 0:
                quantity_needed_with_waste = quantity_needed * (1 + config.waste_threshold_kg / 100)
            else:
                quantity_needed_with_waste = quantity_needed
            
            # Get available lots (FIFO order)
            lots = IngredientLot.objects.filter(
                ingredient=ingredient,
                is_active=True
            ).order_by('received_date', 'created_at')
            
            available_stock = sum(lot.quantity_current for lot in lots)
            
            results.append({
                'ingredient': ingredient,
                'needed': quantity_needed,
                'needed_with_waste': quantity_needed_with_waste,
                'available': available_stock,
                'sufficient': available_stock >= quantity_needed_with_waste
            })
            
            if available_stock < quantity_needed_with_waste:
                all_available = False
        
        return {
            'available': all_available,
            'details': results
        }
    
    @staticmethod
    @transaction.atomic
    def consume_ingredients_fifo(ingredient, quantity_needed):
        """
        Consume ingredients using FIFO logic.
        Returns list of consumption records.
        
        CRITICAL: This method handles waste logic automatically.
        Small remainders are marked as waste.
        """
        config = TraceabilityConfig.get_config()
        consumptions = []
        
        # Get active lots ordered by FIFO
        lots = IngredientLot.objects.filter(
            ingredient=ingredient,
            is_active=True
        ).order_by('received_date', 'created_at')
        
        remaining = Decimal(str(quantity_needed))
        
        for lot in lots:
            if remaining <= 0:
                break
            
            # Determine how much to take from this lot
            to_consume = min(lot.quantity_current, remaining)
            
            # Consume from lot
            lot.consume(to_consume)
            
            consumptions.append({
                'lot': lot,
                'quantity': to_consume,
                'is_waste': False
            })
            
            remaining -= to_consume
            
            # Check if remainder should be wasted
            if config.waste_threshold_kg > 0 and lot.quantity_current <= config.waste_threshold_kg and lot.quantity_current > 0:
                # Mark remainder as waste
                waste_amount = lot.quantity_current
                lot.consume(waste_amount)
                lot.is_wasted = True
                lot.save()
                
                consumptions.append({
                    'lot': lot,
                    'quantity': waste_amount,
                    'is_waste': True
                })
        
        if remaining > 0:
            raise ValidationError(
                f"Stock insuficiente de {ingredient.name}. Falta: {remaining} kg"
            )
        return consumptions
    
    @staticmethod
    @transaction.atomic
    def register_production(product, bom, quantity_produced, internal_lot_code, 
                           user=None, notes=None, production_date=None, production_order=None):
        """
        Registra una producción completa:
        1. Verifica stock
        2. Consume ingredientes (FIFO + waste logic)
        3. Crea ProductionBatch
        4. Registra BatchConsumptions
        5. Actualiza Stock del Producto Final
        
        Returns:
            ProductionBatch created
        """
        if production_date is None:
            production_date = date.today()
        
        # Step 1: Check stock availability
        stock_check = ProductionService.check_stock_availability(bom, quantity_produced)
        if not stock_check['available']:
            insufficient = [d for d in stock_check['details'] if not d['sufficient']]
            error_msg = "Stock insuficiente para los siguientes ingredientes:\n"
            for d in insufficient:
                unit_label = "unidades" if d['ingredient'].type == 'supply' else "kg"
                error_msg += f"- {d['ingredient'].name}: Necesarios {d['needed_with_waste']} {unit_label}, Disponibles {d['available']} {unit_label} (Tu Stock)\n"
            raise ValidationError(error_msg)
        
        # Step 2: Consume ingredients
        all_consumptions = []
        for bom_line in bom.lines.all():
            ingredient = bom_line.ingredient
            if not ingredient:
                continue
            
            # Calculate quantity needed based on ingredient type
            if ingredient.type == 'supply':
                # Supplies are UNITS (e.g. 1 spoon per product)
                quantity_needed_in_kg = Decimal(str(quantity_produced)) * bom_line.quantity
            else:
                # Raw Materials are PERCENTAGES
                percentage = bom_line.quantity
                bom_base_kg = bom.quantity if bom.quantity else Decimal('0.1')
                quantity_per_unit_kg = (percentage / 100) * bom_base_kg
                quantity_needed_in_kg = Decimal(str(quantity_produced)) * quantity_per_unit_kg / bom_base_kg
            
            # Consume using FIFO
            consumptions_data = ProductionService.consume_ingredients_fifo(
                ingredient, quantity_needed_in_kg
            )
            
            all_consumptions.extend(consumptions_data)
        
        # Step 3: Create ProductionBatch
        batch = ProductionBatch.objects.create(
            product=product,
            bom=bom,
            quantity_produced=quantity_produced,
            internal_lot_code=internal_lot_code,
            production_date=production_date,
            status='COMPLETED',
            notes=notes,
            user=user,
            production_order=production_order
        )
        
        # Step 4: Register consumptions
        for data in all_consumptions:
            BatchConsumption.objects.create(
                production_batch=batch,
                ingredient_lot=data['lot'],
                ingredient=data['lot'].ingredient,
                quantity_consumed=data['quantity'],
                is_waste=data['is_waste']
            )
            
        # Step 5: Update Product Stock (Inventory)
        # Assuming quantity_produced is units (or aligned with stock_quantity unit)
        # Using F expression to avoid race conditions
        from django.db.models import F
        product.stock_quantity = F('stock_quantity') + int(quantity_produced)
        product.save()
        
        return batch


class AlertService:
    """Servicio para gestión de alertas de trazabilidad."""
    
    @staticmethod
    def check_new_lot_alerts(lot):
        """Verifica y crea alertas para un nuevo lote."""
        config = TraceabilityConfig.get_config()
        
        # Check expiry
        if lot.expiration_date:
            days_to_expiry = (lot.expiration_date - date.today()).days
            if days_to_expiry <= config.expiry_alert_days:
                StockAlert.objects.create(
                    alert_type='EXPIRY',
                    ingredient_lot=lot,
                    message=f"El lote {lot.internal_id} vence en {days_to_expiry} días"
                )
        
        # Check low stock for this ingredient
        total_stock = IngredientLot.objects.filter(
            ingredient=lot.ingredient,
            is_active=True
        ).aggregate(total=Sum('quantity_current'))['total'] or Decimal('0')
        
        if total_stock <= config.low_stock_threshold_kg:
            # Check if alert already exists
            existing = StockAlert.objects.filter(
                alert_type='LOW_STOCK',
                ingredient_lot__ingredient=lot.ingredient,
                is_resolved=False
            ).exists()
            
            if not existing:
                StockAlert.objects.create(
                    alert_type='LOW_STOCK',
                    ingredient_lot=lot,
                    message=f"Stock bajo de {lot.ingredient.name}: {total_stock} kg"
                )
    
    @staticmethod
    def check_all_alerts(user):
        """Verifica todas las alertas activas y crea nuevas si es necesario."""
        config = TraceabilityConfig.get_config()
        
        # Check expiry for all active lots
        for lot in IngredientLot.objects.filter(is_active=True, user=user):
            AlertService.check_new_lot_alerts(lot)


class TraceabilityService:
    """Servicio para consultas de trazabilidad completa."""
    
    @staticmethod
    def get_production_traceability(production_batch):
        """
        Obtiene trazabilidad completa de un lote de producción.
        
        Returns:
            dict con detalles completos de ingredientes consumidos
        """
        result = {
            'batch': production_batch,
            'consumptions': []
        }
        
        # Group consumptions by ingredient
        ingredients_used = production_batch.consumptions.values_list(
            'ingredient', flat=True
        ).distinct()
        
        for ingredient_id in ingredients_used:
            ingredient = Ingredient.objects.get(pk=ingredient_id)
            
            ingredient_consumptions = production_batch.consumptions.filter(
                ingredient=ingredient
            ).select_related('ingredient_lot')
            
            lots_used = []
            total_consumed = Decimal('0')
            
            for consumption in ingredient_consumptions:
                lots_used.append({
                    'lot': consumption.ingredient_lot,
                    'quantity': consumption.quantity_consumed,
                    'is_waste': consumption.is_waste
                })
                if not consumption.is_waste:
                    total_consumed += consumption.quantity_consumed
            
            result['consumptions'].append({
                'ingredient': ingredient,
                'total_consumed': total_consumed,
                'lots_used': lots_used
            })
        
        return result


class SalesTraceabilityService:
    """Gestiona la asignación automática de lotes de producción a ventas."""
    
    @staticmethod
    @transaction.atomic
    def auto_allocate_sale(sale):
        from .models import SaleBatchAllocation
        allocations_created = []
        errors = []
        for sale_item in sale.items.all():
            try:
                existing = sale_item.batch_allocations.aggregate(total=Sum('quantity_allocated'))['total'] or Decimal('0')
                if sale_item.product and sale_item.product.weight_kg:
                    needed_kg = (Decimal(str(sale_item.quantity)) * sale_item.product.weight_kg) - existing
                else:
                    needed_kg = Decimal(str(sale_item.quantity)) - existing
                if needed_kg <= 0:
                    continue
                batches = ProductionBatch.objects.filter(product=sale_item.product, status='COMPLETED', quantity_remaining__gt=0).order_by('production_date', 'created_at')
                remaining_needed = needed_kg
                for batch in batches:
                    if remaining_needed <= 0:
                        break
                    to_allocate = min(batch.quantity_remaining, remaining_needed)
                    allocation = SaleBatchAllocation.objects.create(sale_item=sale_item, production_batch=batch, quantity_allocated=to_allocate, user=getattr(sale, 'user', None))
                    batch.allocate(to_allocate)
                    allocations_created.append(allocation)
                    remaining_needed -= to_allocate
                if remaining_needed > 0:
                    errors.append({'sale_item': sale_item, 'product': sale_item.product, 'missing_kg': remaining_needed})
            except Exception as e:
                errors.append({'sale_item': sale_item, 'error': str(e)})
        if errors:
            raise ValidationError({'detail': 'Stock insuficiente', 'errors': errors})
        return {'success': True, 'allocations': allocations_created, 'total_allocated': len(allocations_created)}
    
    @staticmethod
    def get_sale_traceability(sale):
        result = {'sale': sale, 'customer': getattr(sale, 'customer', None), 'items': []}
        for sale_item in sale.items.all():
            item_trace = {'sale_item': sale_item, 'product': sale_item.product, 'batches_used': []}
            for allocation in sale_item.batch_allocations.all():
                batch = allocation.production_batch
                ingredients_used = []
                for consumption in batch.consumptions.all():
                    ingredients_used.append({'ingredient': consumption.ingredient, 'ingredient_lot': consumption.ingredient_lot, 'quantity': consumption.quantity_consumed, 'supplier_lot': consumption.ingredient_lot.supplier_lot})
                item_trace['batches_used'].append({'batch': batch, 'allocated_kg': allocation.quantity_allocated, 'ingredients': ingredients_used})
            result['items'].append(item_trace)
        return result
