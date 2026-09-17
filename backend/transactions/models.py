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


class Transaction(models.Model):
    id = models.BigAutoField(primary_key=True)

    company = models.ForeignKey(
        "tenancy.Company",
        on_delete=models.CASCADE,
        related_name="erp_transactions",
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
        db_table = "transaction"
        ordering = ["-tran_date", "-id"]

        constraints = [
            models.UniqueConstraint(
                fields=["company", "tran_id"],
                name="unique_transaction_tran_id_company",
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
                name="tx__type_record_date_idx",
            ),
            models.Index(
                fields=["company", "entity"],
                name="tx_company_entity_idx",
            ),
        ]

    def __str__(self):
        return f"{self.tran_id} — {self.name or self.entity}"
