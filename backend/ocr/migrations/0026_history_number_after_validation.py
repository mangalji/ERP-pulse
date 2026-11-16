from django.db import migrations, models


def clear_unvalidated_history_numbers(apps, schema_editor):
    OCRBatch = apps.get_model("ocr", "OCRBatch")
    OCRValidationResult = apps.get_model("ocr", "OCRValidationResult")

    validated_batch_ids = set()
    for validation in OCRValidationResult.objects.select_related("document").iterator():
        document = validation.document
        batch_id = document.batch_id
        if batch_id is None and document.upload_id:
            batch_id = document.upload.batch_id
        if batch_id is not None:
            validated_batch_ids.add(batch_id)

    if validated_batch_ids:
        OCRBatch.objects.exclude(pk__in=validated_batch_ids).update(history_number=None)
    else:
        OCRBatch.objects.all().update(history_number=None)


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0025_aiconfiguration_configured_by_and_last_error"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ocrbatch",
            name="history_number",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                editable=False,
                null=True,
                unique=True,
            ),
        ),
        migrations.RunPython(clear_unvalidated_history_numbers, migrations.RunPython.noop),
    ]
