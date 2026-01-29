"""
Script de migración de datos desde archivos Excel del sistema de trazabilidad antiguo
a modelos Django. Este script se ejecuta UNA VEZ para importar datos históricos.

Uso:
    python manage.py shell < scripts/migrate_traceability_from_excel.py
    
O:
    python manage.py shell
    >>> exec(open('scripts/migrate_traceability_from_excel.py').read())
"""

import os
import sys
import django
from pathlib import Path
from decimal import Decimal
from datetime import datetime

# Setup Django
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core_erp.settings')
django.setup()

# Imports después de setup
import pandas as pd
from django.utils import timezone
from traceability.models import (
    IngredientLot,
    ProductionBatch,
    BatchConsumption,
    TraceabilityConfig
)
from traceability.services import StockService, ProductionService
from inventory.models import Ingredient, Product
from production.models import BillOfMaterial, BomLine
from django.contrib.auth.models import User


# Las recetas del ERP se mantienen como están.
# El archivo RECETAS_CONFIG.py era solo un ejemplo del sistema antiguo.
# No se migran recetas, solo stock de ingredientes.


def migrate_stock_from_excel():
    """Migra stock desde DB_STOCK.xlsx a IngredientLot."""
    excel_path = BASE_DIR / 'Planillas de Trazabilidad' / 'Sistema_Trazabilidad' / 'DB_STOCK.xlsx'
    
    if not excel_path.exists():
        print(f"⚠ No se encontró {excel_path}")
        print("  Continúa sin migrar stock...\n")
        return
    
    print("\n" + "="*60)
    print("MIGRANDO STOCK DESDE DB_STOCK.xlsx")
    print("="*60 + "\n")
    
    try:
        df = pd.read_excel(excel_path)
        user = User.objects.first()
        
        for _, row in df.iterrows():
            # Buscar ingrediente por nombre
            ingredient_name = row['Materia_Prima']
            ingredient = Ingredient.objects.filter(name=ingredient_name).first()
            
            if not ingredient:
                print(f"⚠ Ingrediente no encontrado: {ingredient_name}, creando...")
                ingredient = Ingredient.objects.create(
                    name=ingredient_name,
                    user=user,
                    type='raw_material',
                    unit='kg'
                )
            
            # Parsear fecha de vencimiento
            vto_str = row.get('Vto')
            expiration_date = None
            if pd.notna(vto_str):
                try:
                    expiration_date = pd.to_datetime(vto_str).date()
                except:
                    pass
            
            # Solo crear lote si tiene stock activo
            if pd.notna(row['Stock_Actual']) and float(row['Stock_Actual']) > 0:
                lot, created = IngredientLot.objects.get_or_create(
                    internal_id=row['ID_Interno'],
                    defaults={
                        'user': user,
                        'ingredient': ingredient,
                        'quantity_initial': Decimal(str(row['Stock_Inicial'])),
                        'quantity_current': Decimal(str(row['Stock_Actual'])),
                        'supplier_lot': row['Lote_Prov'],
                        'expiration_date': expiration_date,
                        'is_active': True
                    }
                )
                
                if created:
                    print(f"✓ Lote importado: {row['ID_Interno']} - {ingredient_name} ({row['Stock_Actual']} kg)")
                else:
                    print(f"○ Lote ya existe: {row['ID_Interno']}")
        
        print(f"\n✓ Migración de stock completada!\n")
        
    except Exception as e:
        print(f"✗ Error al migrar stock: {e}\n")


def create_initial_config():
    """Crea configuración inicial del sistema de trazabilidad."""
    print("\n" + "="*60)
    print("CREANDO CONFIGURACIÓN INICIAL")
    print("="*60 + "\n")
    
    config = TraceabilityConfig.get_config()
    print(f"✓ Configuración creada/obtenida:")
    print(f"  - Umbral de merma: {config.waste_threshold_kg} kg")
    print(f"  - Umbral stock bajo: {config.low_stock_threshold_kg} kg")
    print(f"  - Días para alerta de vencimiento: {config.expiry_alert_days} días")
    print()


def main():
    """Ejecuta la migración completa."""
    print("\n" + "="*70)
    print(" "*15 + "MIGRACIÓN DE TRAZABILIDAD")
    print("="*70)
    print("\nNOTA: Las recetas del ERP se mantienen como están.")
    print("Solo se migra stock de ingredientes desde DB_STOCK.xlsx si existe.\n")
    
    # 1. Migrar stock desde Excel (si existe)
    migrate_stock_from_excel()
    
    # 2. Crear configuración inicial
    create_initial_config()
    
    # 3. Generar alertas iniciales
    print("="*60)
    print("GENERANDO ALERTAS INICIALES")
    print("="*60 + "\n")
    StockService.check_and_create_alerts()
    print("✓ Alertas generadas\n")
    
    print("="*70)
    print(" "*20 + "¡MIGRACIÓN COMPLETADA!")
    print("="*70)
    print("\nPuedes acceder al sistema de trazabilidad en:")
    print("  - Stock: /traceability/stock/")
    print("  - Registrar producción: /traceability/production/create/")
    print("  - Historial: /traceability/production/history/")
    print("\nRECUERDA: Usa tus recetas existentes (BillOfMaterial) del ERP.")
    print()


if __name__ == '__main__':
    main()
