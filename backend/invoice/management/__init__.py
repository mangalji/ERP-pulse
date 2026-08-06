from django.core.management.base import BaseCommand
from invoice.models import InvoiceNetSuiteMapping


class Command(BaseCommand):
    help = 'Seed InvoiceNetSuiteMapping with default field mappings'

    def handle(self, *args, **options):
        mappings = [
            {'invoice_field': 'vendor', 'netsuite_field': 'entity', 'is_required': True},
            {'invoice_field': 'invoice_number', 'netsuite_field': 'tranid', 'is_required': True},
            {'invoice_field': 'invoice_date', 'netsuite_field': 'trandate', 'is_required': True},
            {'invoice_field': 'currency', 'netsuite_field': 'currency', 'is_required': True},
            {'invoice_field': 'total_amount', 'netsuite_field': 'total', 'is_required': True},
            {'invoice_field': 'tax_amount', 'netsuite_field': 'taxtotal', 'is_required': False},
            {'invoice_field': 'subtotal', 'netsuite_field': 'subtotal', 'is_required': False},
            {'invoice_field': 'gst', 'netsuite_field': 'gst', 'is_required': False},
            {'invoice_field': 'purchase_order', 'netsuite_field': 'poreference', 'is_required': False},
            {'invoice_field': 'remarks', 'netsuite_field': 'memo', 'is_required': False},
        ]
        for m in mappings:
            obj, created = InvoiceNetSuiteMapping.objects.get_or_create(
                invoice_field=m['invoice_field'],
                defaults={
                    'netsuite_field': m['netsuite_field'],
                    'is_required': m['is_required'],
                    'is_active': True,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created mapping: {obj}'))
            else:
                self.stdout.write(f'Mapping already exists: {obj}')
