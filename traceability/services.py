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


class StockService:
    """Servicio para gestión de stock e ingreso de compras."""
    
    @staticmethod
    def get_next_internal_id(ingredient):
        """
        Genera el siguiente ID interno para un ingrediente.
        Formato: MP-{CODIGO}-{NUMERO}
        Ejemplo: MP-MAL-001, MP-MAL-002, etc.
        """
        # Generar código de 3 letras del ingrediente
        name_parts = ingredient.name.upper().split()
        if len(name_parts) >= 2:
            code = name_parts[0][:3]
        else:
            code = ingredient.name.upper()[:3]
        
        # Buscar el último número usado para este ingrediente
        prefix = f"MP-{code}-"
        last_lot = IngredientLot.objects.filter(
            internal_id__startswith=prefix
        ).order_by('-internal_id').first()
        
        if last_lot:
            # Extraer número y sumar 1
            try:
                last_number = int(last_lot.internal_id.split('-')[-1])
                next_number = last_number + 1
            except (ValueError, IndexError):
                next_number = 1
        else:
            next_number = 1
        
        return f"{prefix}{next_number:03d}"
    
    @staticmethod
    @transaction.atomic
    def register_purchase(ingredient, quantity, supplier_lot, expiration_date, user=None):
        """
        Registra una compra/ingreso de stock.
        
        Args:
            ingredient: Objeto Ingredient
            quantity: Cantidad en kg (Decimal)
            supplier_lot: Lote del proveedor (str)
            expiration_date: Fecha de vencimiento (date o None)
            user: Usuario que registra (User o None)
        
        Returns:
            IngredientLot creado
        """
        # Generar ID único
        internal_id = StockService.get_next_internal_id(ingredient)
        
        # Crear lote
        lot = IngredientLot.objects.create(
            user=user,
            internal_id=internal_id,
            ingredient=ingredient,
            quantity_initial=quantity,
            quantity_current=quantity,
            supplier_lot=supplier_lot,
            expiration_date=expiration_date,
            is_active=True
        )
        
        # Actualizar stock del ingrediente
        ingredient.stock_quantity = Decimal(ingredient.stock_quantity or 0) + quantity
        ingredient.save()
        
        return lot
    
    @staticmethod
    def get_stock_summary():
        """
        Obtiene resumen de stock por ingrediente con alertas.
        
        Returns:
            dict con estructura:
            {
                'ingredients': [
                    {
                        'ingredient': Ingredient,
                        'total_stock': Decimal,
                        'active_lots_count': int,
                        'is_low': bool,
                        'lots': QuerySet de IngredientLots activos
                    },
                    ...
                ],
                'alerts': QuerySet de StockAlerts activas
            }
        """
        config = TraceabilityConfig.get_config()
        ingredients_data = []
        
        for ingredient in Ingredient.objects.all():
            lots = IngredientLot.objects.filter(
                ingredient=ingredient,
                is_active=True
            )
            
            total_stock = lots.aggregate(
                total=Sum('quantity_current')
            )['total'] or Decimal('0')
            
            is_low = total_stock < config.low_stock_threshold_kg
            
            ingredients_data.append({
                'ingredient': ingredient,
                'total_stock': total_stock,
                'active_lots_count': lots.count(),
                'is_low': is_low,
                'lots': lots
            })
        
        # Obtener alertas activas
        alerts = StockAlert.objects.filter(is_resolved=False)
        
        return {
            'ingredients': ingredients_data,
            'alerts': alerts
        }
    
    @staticmethod
    def check_and_create_alerts():
        """
        Verifica stock y vencimientos, creando alertas si es necesario.
        """
        config = TraceabilityConfig.get_config()
        expiry_threshold = date.today() + timedelta(days=config.expiry_alert_days)
        
        # Alertas de stock bajo
        for ingredient in Ingredient.objects.all():
            total_stock = IngredientLot.objects.filter(
                ingredient=ingredient,
                is_active=True
            ).aggregate(total=Sum('quantity_current'))['total'] or Decimal('0')
            
            if total_stock < config.low_stock_threshold_kg:
                # Verificar si ya existe alerta activa
                existing = StockAlert.objects.filter(
                    alert_type='LOW_STOCK',
                    ingredient=ingredient,
                    is_resolved=False
                ).exists()
                
                if not existing:
                    StockAlert.objects.create(
                        alert_type='LOW_STOCK',
                        ingredient=ingredient,
                        message=f"Stock bajo de {ingredient.name}: {total_stock} kg (umbral: {config.low_stock_threshold_kg} kg)"
                    )
        
        # Alertas de vencimiento próximo
        near_expiry_lots = IngredientLot.objects.filter(
            is_active=True,
            expiration_date__lte=expiry_threshold,
            expiration_date__gte=date.today()
        )
        
        for lot in near_expiry_lots:
            existing = StockAlert.objects.filter(
                alert_type='NEAR_EXPIRY',
                ingredient_lot=lot,
                is_resolved=False
            ).exists()
            
            if not existing:
                days_left = (lot.expiration_date - date.today()).days
                StockAlert.objects.create(
                    alert_type='NEAR_EXPIRY',
                    ingredient_lot=lot,
                    ingredient=lot.ingredient,
                    message=f"Lote {lot.internal_id} vence en {days_left} días ({lot.expiration_date})"
                )
        
        # Alertas de vencidos
        expired_lots = IngredientLot.objects.filter(
            is_active=True,
            expiration_date__lt=date.today()
        )
        
        for lot in expired_lots:
            existing = StockAlert.objects.filter(
                alert_type='EXPIRED',
                ingredient_lot=lot,
                is_resolved=False
            ).exists()
            
            if not existing:
                StockAlert.objects.create(
                    alert_type='EXPIRED',
                    ingredient_lot=lot,
                    ingredient=lot.ingredient,
                    message=f"Lote {lot.internal_id} VENCIDO desde {lot.expiration_date}"
                )


class ProductionService:
    """Servicio para registro de producción con trazabilidad."""
    
    @staticmethod
    def check_stock_availability(bom, quantity_to_produce):
        """
        Verifica si hay stock suficiente para producir.
        
        Args:
            bom: BillOfMaterial
            quantity_to_produce: Cantidad a producir en kg
        
        Returns:
            dict con estructura:
            {
                'available': bool,
                'missing': [
                    {'ingredient': Ingredient, 'needed': Decimal, 'available': Decimal},
                    ...
                ]
            }
        """
        missing = []
        
        for bom_line in bom.lines.all():
            if bom_line.ingredient:
                # Calcular cantidad necesaria
                quantity_per_unit = bom_line.quantity / 1000  # convertir g a kg
                total_needed = quantity_per_unit * quantity_to_produce
                
                # Obtener stock disponible
                available = IngredientLot.objects.filter(
                    ingredient=bom_line.ingredient,
                    is_active=True
                ).aggregate(total=Sum('quantity_current'))['total'] or Decimal('0')
                
                if available < total_needed:
                    missing.append({
                        'ingredient': bom_line.ingredient,
                        'needed': total_needed,
                        'available': available
                    })
        
        return {
            'available': len(missing) == 0,
            'missing': missing
        }
    
    @staticmethod
    def consume_ingredients_fifo(ingredient, quantity_needed):
        """
        Consume ingredientes siguiendo FIFO y aplicando lógica de merma.
        
        Args:
            ingredient: Ingredient
            quantity_needed: Cantidad total a consumir (kg)
        
        Returns:
            list de dict con estructura:
            [
                {
                    'lot': IngredientLot,
                    'quantity': Decimal,
                    'is_waste': bool
                },
                ...
            ]
        """
        config = TraceabilityConfig.get_config()
        consumptions = []
        remaining_needed = Decimal(str(quantity_needed))
        
        # Obtener lotes ordenados por FIFO (más viejos primero)
        lots = IngredientLot.objects.filter(
            ingredient=ingredient,
            is_active=True
        ).order_by('received_date', 'created_at')
        
        for lot in lots:
            if remaining_needed <= 0:
                break
            
            # Determinar cuánto consumir de este lote
            to_consume = min(lot.quantity_current, remaining_needed)
            
            # Registrar consumo
            consumptions.append({
                'lot': lot,
                'quantity': to_consume,
                'is_waste': False
            })
            
            # Actualizar lote
            lot.quantity_current -= to_consume
            remaining_needed -= to_consume
            
            # Verificar merma
            if lot.quantity_current < config.waste_threshold_kg and lot.quantity_current > 0:
                # Descartar como merma
                consumptions.append({
                    'lot': lot,
                    'quantity': lot.quantity_current,
                    'is_waste': True
                })
                lot.quantity_current = Decimal('0')
                lot.is_wasted = True
            
            # Marcar como inactivo si se agotó
            if lot.quantity_current <= 0:
                lot.is_active = False
            
            lot.save()
        
        if remaining_needed > 0:
            raise ValidationError(
                f"Stock insuficiente de {ingredient.name}. Falta: {remaining_needed} kg"
            )
        
        return consumptions
    
    @staticmethod
    @transaction.atomic
    def register_production(product, bom, quantity_produced, internal_lot_code, user=None, notes=None):
        """
        Registra una producción completa con trazabilidad.
        
        Args:
            product: Product
            bom: BillOfMaterial
            quantity_produced: Cantidad producida en kg
            internal_lot_code: Código de lote (ej: L-260129-01)
            user: Usuario
            notes: Notas opcionales
        
        Returns:
            ProductionBatch creado
        """
        # 1. Verificar disponibilidad
        availability = ProductionService.check_stock_availability(bom, quantity_produced)
        if not availability['available']:
            missing_details = '\n'.join([
                f"- {m['ingredient'].name}: necesita {m['needed']} kg, disponible {m['available']} kg"
                for m in availability['missing']
            ])
            raise ValidationError(f"Stock insuficiente:\n{missing_details}")
        
        # 2. Crear lote de producción
        production_batch = ProductionBatch.objects.create(
            user=user,
            internal_lot_code=internal_lot_code,
            product=product,
            bom=bom,
            quantity_produced=quantity_produced,
            production_date=date.today(),
            status='IN_PROGRESS',
            notes=notes
        )
        
        # 3. Consumir ingredientes con FIFO
        for bom_line in bom.lines.all():
            if bom_line.ingredient:
                # Calcular cantidad necesaria
                quantity_per_unit = bom_line.quantity / 1000  # g a kg
                total_needed = quantity_per_unit * quantity_produced
                
                # Consumir con FIFO
                consumptions = ProductionService.consume_ingredients_fifo(
                    bom_line.ingredient, 
                    total_needed
                )
                
                # Registrar consumos en BatchConsumption
                for consumption in consumptions:
                    BatchConsumption.objects.create(
                        production_batch=production_batch,
                        ingredient_lot=consumption['lot'],
                        ingredient=bom_line.ingredient,
                        quantity_consumed=consumption['quantity'],
                        is_waste=consumption['is_waste']
                    )
                
                # Actualizar stock del ingrediente
                bom_line.ingredient.stock_quantity = Decimal(
                    bom_line.ingredient.stock_quantity or 0
                ) - total_needed
                if bom_line.ingredient.stock_quantity < 0:
                    bom_line.ingredient.stock_quantity = Decimal('0')
                bom_line.ingredient.save()
        
        # 4. Actualizar stock del producto
        product.stock_quantity += int(quantity_produced)
        product.save()
        
        # 5. Marcar producción como completada
        production_batch.status = 'COMPLETED'
        production_batch.save()
        
        # 6. Verificar alertas
        StockService.check_and_create_alerts()
        
        return production_batch


class TraceabilityService:
    """Servicio para consultas de trazabilidad."""
    
    @staticmethod
    def get_production_history(limit=None, product=None):
        """
        Obtiene historial de producciones.
        
        Args:
            limit: Límite de resultados (None = todos)
            product: Filtrar por producto (None = todos)
        
        Returns:
            QuerySet de ProductionBatch
        """
        queryset = ProductionBatch.objects.select_related('product', 'bom').all()
        
        if product:
            queryset = queryset.filter(product=product)
        
        if limit:
            queryset = queryset[:limit]
        
        return queryset
    
    @staticmethod
    def get_batch_traceability(production_batch):
        """
        Obtiene trazabilidad completa de un lote de producción.
        
        Args:
            production_batch: ProductionBatch
        
        Returns:
            dict con estructura:
            {
                'batch': ProductionBatch,
                'consumptions': [
                    {
                        'ingredient': Ingredient,
                        'total_consumed': Decimal,
                        'lots_used': [
                            {'lot': IngredientLot, 'quantity': Decimal, 'is_waste': bool},
                            ...
                        ]
                    },
                    ...
                ]
            }
        """
        consumptions_data = []
        
        # Agrupar por ingrediente
        ingredients = set(
            consumption.ingredient 
            for consumption in production_batch.consumptions.all()
        )
        
        for ingredient in ingredients:
            lots_used = []
            total_consumed = Decimal('0')
            
            ingredient_consumptions = production_batch.consumptions.filter(
                ingredient=ingredient
            ).select_related('ingredient_lot')
            
            for consumption in ingredient_consumptions:
                lots_used.append({
                    'lot': consumption.ingredient_lot,
                    'quantity': consumption.quantity_consumed,
                    'is_waste': consumption.is_waste
                })
                if not consumption.is_waste:
                    total_consumed += consumption.quantity_consumed
            
            consumptions_data.append({
                'ingredient': ingredient,
                'total_consumed': total_consumed,
                'lots_used': lots_used
            })
        
        return {
            'batch': production_batch,
            'consumptions': consumptions_data
        }
