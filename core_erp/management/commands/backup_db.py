"""
Backup Database Management Command

Creates timestamped backups of the SQLite database.
Keeps the last 7 backups and auto-deletes older ones.

Usage:
    python manage.py backup_db
"""

import shutil
import logging
from pathlib import Path
from datetime import datetime

from django.core.management.base import BaseCommand
from django.conf import settings

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Crea un backup de la base de datos SQLite'

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep', type=int, default=7,
            help='Cantidad de backups a conservar (default: 7)'
        )

    def handle(self, *args, **options):
        keep = options['keep']
        db_path = Path(settings.DATABASES['default']['NAME'])

        if not db_path.exists():
            self.stderr.write(self.style.ERROR(
                f'Base de datos no encontrada: {db_path}'
            ))
            return

        # Create backups directory
        backup_dir = db_path.parent / 'backups'
        backup_dir.mkdir(exist_ok=True)

        # Generate timestamped filename
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        backup_name = f'db_{timestamp}.sqlite3'
        backup_path = backup_dir / backup_name

        # Copy database
        try:
            shutil.copy2(str(db_path), str(backup_path))
            size_mb = backup_path.stat().st_size / (1024 * 1024)
            self.stdout.write(self.style.SUCCESS(
                f'[OK] Backup creado: {backup_name} ({size_mb:.1f} MB)'
            ))
            logger.info(f'Database backup created: {backup_path}')
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'[ERROR] Error al crear backup: {e}'))
            logger.error(f'Backup failed: {e}')
            return

        # Cleanup old backups (keep only the most recent N)
        existing = sorted(
            backup_dir.glob('db_*.sqlite3'),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        )

        deleted = 0
        for old_backup in existing[keep:]:
            try:
                old_backup.unlink()
                deleted += 1
                logger.info(f'Old backup deleted: {old_backup.name}')
            except Exception as e:
                logger.error(f'Failed to delete old backup {old_backup.name}: {e}')

        if deleted:
            self.stdout.write(self.style.WARNING(
                f'[CLEANUP] {deleted} backup(s) antiguos eliminados (conservando {keep})'
            ))

        total = len(list(backup_dir.glob('db_*.sqlite3')))
        self.stdout.write(f'[INFO] Total backups: {total} en {backup_dir}')
