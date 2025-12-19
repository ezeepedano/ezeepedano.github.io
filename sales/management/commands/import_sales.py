
from django.core.management.base import BaseCommand, CommandError
from sales.utils import process_sales_file
from sales.models import Sale, SaleItem
import os

class Command(BaseCommand):
    help = 'Imports sales from a MercadoLibre Excel export file'

    def add_arguments(self, parser):
        parser.add_argument('file_path', type=str, help='Path to the Excel file')
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear all existing sales data before importing',
        )

    def handle(self, *args, **options):
        file_path = options['file_path']
        clear_first = options['clear']

        if not os.path.exists(file_path):
            raise CommandError(f'File "{file_path}" does not exist')

        if clear_first:
            self.stdout.write(self.style.WARNING('Clearing all existing Sales and SaleItems...'))
            SaleItem.objects.all().delete()
            Sale.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('Data cleared.'))

        self.stdout.write(f'Importing from "{file_path}"...')

        try:
            with open(file_path, 'rb') as f:
                stats = process_sales_file(f)
            
            if 'error' in stats:
                raise CommandError(f"Import failed: {stats['error']}")
            
            self.stdout.write(self.style.SUCCESS("Import successful!"))
            self.stdout.write(f"  New Sales: {stats['new_sales']}")
            self.stdout.write(f"  Updated Sales: {stats['existing_sales']}")
            self.stdout.write(f"  Errors: {stats['errors']}")
            if stats['products_not_found']:
                 self.stdout.write(self.style.WARNING(f"  Products Not Found (Not Linked): {len(stats['products_not_found'])}"))

        except Exception as e:
            raise CommandError(f'Error processing file: {e}')
