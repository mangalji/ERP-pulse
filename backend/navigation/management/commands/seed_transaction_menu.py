from django.core.management.base import BaseCommand
from django.db import transaction

from navigation.models import TransactionMenu, TransactionMenuItem


class Command(BaseCommand):
    help = "Seed the single parent and shared child table for the transaction menu."

    def handle(self, *args, **options):
        with transaction.atomic():
            transaction_menu, _ = TransactionMenu.objects.update_or_create(
                key="transactions",
                defaults={
                    "name": "Transactions",
                    "icon": "transaction",
                    "module_code": "transactions",
                    "requires_netsuite": True,
                    "is_active": True,
                    "sort_order": 100,
                },
            )

            definitions = [
                {
                    "key": "sales",
                    "name": "Sales",
                    "parent_key": None,
                    "route": "",
                    "query_params": {},
                    "icon": "sales",
                    "sort_order": 10,
                },
                {
                    "key": "sales_orders",
                    "name": "Sales Orders",
                    "parent_key": "sales",
                    "route": "/app/transactions",
                    "query_params": {"view": "sales_orders"},
                    "icon": "sales_order",
                    "sort_order": 10,
                },
                # {
                #     "key": "sales_invoices",
                #     "name": "Invoices",
                #     "parent_key": "sales",
                #     "route": "/app/transactions",
                #     "query_params": {"view": "sales_invoices"},
                #     "icon": "invoice",
                #     "sort_order": 20,
                # },
                {
                    "key": "cash_sales",
                    "name": "Cash Sales",
                    "parent_key": "sales",
                    "route": "/app/transactions",
                    "query_params": {"view": "cash_sales"},
                    "icon": "cash_sale",
                    "sort_order": 30,
                },
                {
                    "key": "purchases",
                    "name": "Purchases",
                    "parent_key": None,
                    "route": "",
                    "query_params": {},
                    "icon": "purchases",
                    "sort_order": 20,
                },
                {
                    "key": "purchase_orders",
                    "name": "Purchase Orders",
                    "parent_key": "purchases",
                    "route": "/app/transactions",
                    "query_params": {"view": "purchase_orders"},
                    "icon": "purchase_order",
                    "sort_order": 10,
                },
                # {
                #     "key": "vendor_bills",
                #     "name": "Vendor Bills",
                #     "parent_key": "purchases",
                #     "route": "/app/transactions",
                #     "query_params": {"view": "vendor_bills"},
                #     "icon": "vendor_bill",
                #     "sort_order": 20,
                # },
                {
                    "key": "vendor_payments",
                    "name": "Vendor Payments",
                    "parent_key": "purchases",
                    "route": "/app/transactions",
                    "query_params": {"view": "vendor_payments"},
                    "icon": "vendor_payment",
                    "sort_order": 30,
                },
            ]

            items = {}
            for definition in definitions:
                parent_item = None
                if definition["parent_key"]:
                    parent_item = items[definition["parent_key"]]

                item, _ = TransactionMenuItem.objects.update_or_create(
                    key=definition["key"],
                    defaults={
                        "menu": transaction_menu,
                        "parent_item": parent_item,
                        "name": definition["name"],
                        "route": definition["route"],
                        "query_params": definition["query_params"],
                        "icon": definition["icon"],
                        "module_code": "transactions",
                        "requires_netsuite": True,
                        "is_active": True,
                        "sort_order": definition["sort_order"],
                    },
                )
                items[definition["key"]] = item

            expected_keys = {item["key"] for item in definitions}
            TransactionMenuItem.objects.filter(menu=transaction_menu).exclude(
                key__in=expected_keys,
            ).delete()

        self.stdout.write(
            self.style.SUCCESS(
                "Transaction menu seeded: 1 parent + 6 child records."
            )
        )
