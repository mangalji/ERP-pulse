from decimal import Decimal

from django.db import models

def get_model_schema(model):
    fields = []

    for field in model._meta.fields:
        fields.append({
            "name": field.name,
            "label": str(field.verbose_name).replace("_", " ").title(),
            "type": field.get_internal_type(),
            "required": not field.blank and not field.null and field.default is models.NOT_PROVIDED,
            "read_only": field.auto_created or field.primary_key or not field.editable,
        })

    return fields


class Product(models.Model):
    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "tenancy.Company",
        on_delete=models.CASCADE,
        related_name="erp_products",
    )

    # Dynamic values coming from the navigation hierarchy.
    # These are stored in DB but are not displayed as UI columns.
    transaction_type = models.CharField(
        max_length=120,
    )

    record_type = models.CharField(
        max_length=120,
    )

    tran_id = models.CharField(
        max_length=80,
    )

    tran_date = models.DateField()

    # Company / customer / vendor name.
    entity = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    name = models.CharField(
        max_length=255,
        blank=True,
        default="",
    )

    # Temporary text field. Later this can become PDF/image/file handling.
    invoice = models.TextField(
        blank=True,
        default="",
    )

    amount = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=Decimal("0.00"),
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "product"
        ordering = ["-tran_date", "-id"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "tran_id"],
                name="unique_product_tran_id_company",
            )
        ]

        indexes = [
            models.Index(
                fields=[
                    "company",
                    "transaction_type",
                    "record_type",
                    "tran_date",
                ],
                name="pdt__type_record_date_idx",
            ),
            models.Index(
                fields=["company", "entity"],
                name="pdt_company_entity_idx",
            ),
        ]

    def __str__(self):
        return f"{self.tran_id} — {self.name or self.entity}"


# class ProductLine(models.Model):
#     id = models.BigAutoField(primary_key=True)
#     transaction = models.ForeignKey(
#         Product,
#         on_delete=models.CASCADE,
#         related_name="lines",
#     )
#     line_number = models.PositiveIntegerField()
#     item_external_id = models.CharField(max_length=80, blank=True, default="")
#     item_sku = models.CharField(max_length=120, blank=True, default="")
#     item_name = models.CharField(max_length=255)
#     description = models.TextField(blank=True, default="")
#     quantity = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("1.0000"))
#     rate = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
#     amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0.00"))
#     location = models.CharField(max_length=120, blank=True, default="")
#     department = models.CharField(max_length=120, blank=True, default="")
#     created_at = models.DateTimeField(auto_now_add=True)
#     updated_at = models.DateTimeField(auto_now=True)

#     class Meta:
#         db_table = "transaction_line"
#         ordering = ["line_number", "id"]
#         constraints = [
#             models.UniqueConstraint(
#                 fields=["transaction", "line_number"],
#                 name="unique_transaction_line_number",
#             )
#         ]
#         indexes = [
#             models.Index(fields=["transaction", "line_number"], name="tx_line_parent_idx"),
#         ]

#     def __str__(self):
#         return f"{self.transaction.tran_id} / {self.line_number} — {self.item_name}"
