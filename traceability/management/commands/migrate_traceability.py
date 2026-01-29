"""
Management command para migrar datos de trazabilidad desde Excel.

Uso:
    python manage.py migrate_traceability
"""

from django.core.management.base import BaseCommand
from pathlib import Path
import subprocess
import sys


class Command(BaseCommand):
    help = 'Migra datos del sistema de trazabilidad desde archivos Excel a Django'

    def handle(self, *args, **options):
        script_path = Path(__file__).resolve().parent.parent.parent / 'scripts' / 'migrate_traceability_from_excel.py'
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('  MIGRACIÓN DE TRAZABILIDAD'))
        self.stdout.write('='*70 + '\n')
        
        if not script_path.exists():
            self.stdout.write(self.style.ERROR(f'Script no encontrado: {script_path}'))
            return
        
        try:
            # Ejecutar el script
            exec(open(script_path).read())
            
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error durante la migración: {e}'))
            import traceback
            traceback.print_exc()
