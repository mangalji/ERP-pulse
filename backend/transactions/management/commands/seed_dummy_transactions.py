from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction as db_transaction

from tenancy.models import Company
from transactions.models import Transaction, TransactionLine


SALES_ENTITIES = [
    ("CUST-1001", "Acme Retail Pvt Ltd"),
    ("CUST-1002", "Brightline Industries"),
    ("CUST-1003", "Northstar Traders"),
    ("CUST-1004", "Vertex Solutions"),
    ("CUST-1005", "Bluewave Distribution"),
]

VENDOR_ENTITIES = [
    ("VEND-2001", "Global Components Ltd"),
    ("VEND-2002", "Prime Office Supplies"),
    ("VEND-2003", "Atlas Industrial Co"),
    ("VEND-2004", "Metro Packaging Works"),
    ("VEND-2005", "Evergreen Logistics"),
]

ITEMS = [
    ("ITEM-001", "LAPTOP-PRO-14", "Laptop Pro 14", Decimal("75000.00")),
    ("ITEM-002", "MON-27-4K", "27-inch 4K Monitor", Decimal("42000.00")),
    ("ITEM-003", "DOCK-USB-C", "USB-C Docking Station", Decimal("12500.00")),
    ("ITEM-004", "KB-MECH", "Mechanical Keyboard", Decimal("6500.00")),
    ("ITEM-005", "MOUSE-WL", "Wireless Mouse", Decimal("2800.00")),
]


class Command(BaseCommand):
    help = "Create 40 tenant-scoped dummy transactions (10 sales orders + 10 cash sales + 10 purchase orders + 10 vendor payments)."

    def add_arguments(self, parser):
        parser.add_argument("--company-id", help="Company UUID. Defaults to the first company.")

    def handle(self, *args, **options):
        company_id = options.get("company_id")
        company = self._get_company(company_id)

        with db_transaction.atomic():
            sales_created = self._seed_type(company, Transaction.SALES_ORDER)
            cash_sales_created = self._seed_type(company, Transaction.CASH_SALE)
            purchase_created = self._seed_type(company, Transaction.PURCHASE_ORDER)
            vendor_payments_created = self._seed_type(company, Transaction.VENDOR_PAYMENT)
        
        total_created = (
            sales_created
            + cash_sales_created
            + purchase_created
            + vendor_payments_created
        )
        
        self.stdout.write(self.style.SUCCESS(
            f"Seeded {total_created} dummy transactions for {company.name}: "
            f"{sales_created} sales orders + "
            f"{cash_sales_created} cash sales + "
            f"{purchase_created} purchase orders + "
            f"{vendor_payments_created} vendor payments."
        ))

    def _get_company(self, company_id):
        if company_id:
            try:
                return Company.objects.get(pk=company_id)
            except Company.DoesNotExist as exc:
                raise CommandError(f"Company not found: {company_id}") from exc
        company = Company.objects.order_by("created_at").first()
        if company is None:
            raise CommandError("No company exists. Create a company first or pass --company-id.")
        return company

    def _get_status(self, *, transaction_type, index):
        if transaction_type == Transaction.SALES_ORDER:
            return (
                "Pending Approval"
                if index % 3 == 0
                else "Pending Fulfillment"
            )

        if transaction_type == Transaction.CASH_SALE:
            return (
                "Paid"
                if index % 3 != 0
                else "Pending Payment"
            )

        if transaction_type == Transaction.PURCHASE_ORDER:
            return (
                "Pending Approval"
                if index % 3 == 0
                else "Pending Receipt"
            )

        return (
            "Paid"
            if index % 3 != 0
            else "Pending Payment"
        )
    

    def _seed_type(self, company, transaction_type):
        created_count = 0
        for index in range(1, 11):
            is_sales_order = transaction_type == Transaction.SALES_ORDER
            is_cash_sale = transaction_type == Transaction.CASH_SALE
            is_purchase_order = transaction_type == Transaction.PURCHASE_ORDER
            is_vendor_payment = transaction_type == Transaction.VENDOR_PAYMENT

            is_sales = is_sales_order or is_cash_sale

            if is_sales_order:
                tran_id = f"SO-DUMMY-{index:03d}"
                record_label = "Sales Order"
                source_prefix = "SO"
            elif is_cash_sale:
                tran_id = f"CS-DUMMY-{index:03d}"
                record_label = "Cash Sale"
                source_prefix = "CS"
            elif is_purchase_order:
                tran_id = f"PO-DUMMY-{index:03d}"
                record_label = "Purchase Order"
                source_prefix = "PO"
            else:
                tran_id = f"VP-DUMMY-{index:03d}"
                record_label = "Vendor Payment"
                source_prefix = "VP"

            entity_id, entity_name = (
                SALES_ENTITIES if is_sales else VENDOR_ENTITIES
            )[(index - 1) % 5]

            line_1 = ITEMS[(index - 1) % len(ITEMS)]
            line_2 = ITEMS[index % len(ITEMS)]
            quantity_1 = Decimal(index + 1)
            quantity_2 = Decimal((index % 4) + 1)
            subtotal = (line_1[3] * quantity_1) + (line_2[3] * quantity_2)
            tax = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
            total = subtotal + tax
            transaction_date = date.today() - timedelta(days=index)

            obj, created = Transaction.objects.update_or_create(
                company=company,
                tran_id=tran_id,
                defaults={
                    "transaction_type": transaction_type,
                    "transaction_date": transaction_date,
                    "entity_type": "customer" if is_sales else "vendor",
                    "entity_external_id": entity_id,
                    "entity_name": entity_name,
                    "status": self._get_status(transaction_type=transaction_type, index=index),
                    "currency": "INR",
                    "memo": f"Dummy NetSuite-style {record_label} for development/testing.",
                    "subtotal": subtotal,
                    "tax_total": tax,
                    "total": total,
                    "source_system": "dummy_netsuite_format",
                    "source_record_id": f"DUMMY-{source_prefix}-{index:03d}",
                },
            )

            if created:
                created_count += 1

            TransactionLine.objects.filter(transaction=obj).delete()
            for line_number, item, quantity in (
                (1, line_1, quantity_1),
                (2, line_2, quantity_2),
            ):
                amount = (item[3] * quantity).quantize(Decimal("0.01"))
                TransactionLine.objects.create(
                    transaction=obj,
                    line_number=line_number,
                    item_external_id=item[0],
                    item_sku=item[1],
                    item_name=item[2],
                    description=f"Dummy line {line_number} for {tran_id}",
                    quantity=quantity,
                    rate=item[3],
                    amount=amount,
                    location=(
    "Retail Counter"
    if is_cash_sale
    else ("Main Warehouse" if is_sales else "Supplier Warehouse")
),
department=(
    "Sales"
    if is_sales
    else "Procurement"
),
                )
        return created_count
