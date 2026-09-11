from django.db import models


TYPE_MAP = {
    models.AutoField: "integer",
    models.BigAutoField: "integer",
    models.IntegerField: "integer",
    models.BigIntegerField: "integer",
    models.PositiveIntegerField: "integer",
    models.PositiveBigIntegerField: "integer",
    models.SmallIntegerField: "integer",
    models.PositiveSmallIntegerField: "integer",
    models.FloatField: "number",
    models.DecimalField: "decimal",
    models.BooleanField: "boolean",
    models.DateField: "date",
    models.DateTimeField: "datetime",
    models.TimeField: "time",
    models.EmailField: "string",
    models.URLField: "string",
    models.UUIDField: "string",
    models.TextField: "text",
    models.CharField: "string",
    models.JSONField: "json",
}


def get_model_schema(model):
    fields = []

    for field in model._meta.get_fields():
        if not getattr(field, "concrete", False):
            continue

        if getattr(field, "auto_created", False):
            continue

        internal_type = field.get_internal_type()

        field_type = "string"

        for django_type, frontend_type in TYPE_MAP.items():
            if isinstance(field, django_type):
                field_type = frontend_type
                break

        choices = [
            {
                "value": value,
                "label": label,
            }
            for value, label in (field.choices or [])
        ]

        fields.append({
            "name": field.name,
            "label": field.verbose_name.replace("_", " ").title(),
            "type": field_type,
            "required": (
                not getattr(field, "blank", False)
                and not getattr(field, "null", False)
                and not getattr(field, "auto_created", False)
            ),
            "read_only": (
                getattr(field, "auto_created", False)
                or getattr(field, "primary_key", False)
                or getattr(field, "auto_now", False)
                or getattr(field, "auto_now_add", False)
            ),
            "nullable": getattr(field, "null", False),
            "choices": choices,
        })

    return fields