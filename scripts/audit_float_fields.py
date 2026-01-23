"""
Script de auditoría para detectar FloatFields en contextos financieros.
Ejecutar: python manage.py shell < scripts/audit_float_fields.py
"""

from django.apps import apps
from django.db import models

print("\n" + "="*80)
print("🔍 AUDITORÍA DE CAMPOS FLOAT EN CONTEXTOS FINANCIEROS")
print("="*80 + "\n")

# Palabras clave que indican campos monetarios
MONETARY_KEYWORDS = [
    'price', 'cost', 'amount', 'balance', 'salary', 'wage',
    'total', 'subtotal', 'discount', 'tax', 'vat', 'fee',
    'payment', 'charge', 'revenue', 'expense', 'profit',
    'margin', 'commission', 'bonus', 'pension', 'rate'
]

issues_found = []

for model in apps.get_models():
    for field in model._meta.fields:
        field_type = field.get_internal_type()
        
        # Verificar FloatField
        if field_type == 'FloatField':
            field_name_lower = field.name.lower()
            
            # Verificar si parece ser un campo monetario
            is_monetary = any(keyword in field_name_lower for keyword in MONETARY_KEYWORDS)
            
            if is_monetary:
                issues_found.append({
                    'model': model.__name__,
                    'app': model._meta.app_label,
                    'field': field.name,
                    'severity': 'CRÍTICO'
                })
                print(f"🔴 CRÍTICO: {model._meta.app_label}.{model.__name__}.{field.name}")
            else:
                issues_found.append({
                    'model': model.__name__,
                    'app': model._meta.app_label,
                    'field': field.name,
                    'severity': 'ADVERTENCIA'
                })
                print(f"🟡 ADVERTENCIA: {model._meta.app_label}.{model.__name__}.{field.name} (FloatField - Verificar si es monetario)")

print("\n" + "-"*80)
print(f"RESUMEN: {len(issues_found)} campos FloatField detectados")
print("-"*80)

if issues_found:
    print("\n📝 ACCIONES RECOMENDADAS:\n")
    print("1. Revisar cada campo marcado como CRÍTICO")
    print("2. Crear migración para convertir FloatField → DecimalField(max_digits=14, decimal_places=2)")
    print("3. Actualizar formularios y serializadores")
    print("4. Ejecutar tests completos después de la migración")
    print("\n✅ Ejemplo de migración:")
    print("""
    operations = [
        migrations.AlterField(
            model_name='sale',
            name='amount',
            field=models.DecimalField(max_digits=14, decimal_places=2, default=0),
        ),
    ]
    """)
else:
    print("\n✅ ¡Excelente! No se encontraron FloatFields en campos monetarios.")

print("\n" + "="*80 + "\n")
