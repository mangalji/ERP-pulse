from django.db import migrations, models


def populate_history_numbers(apps, schema_editor):
    OCRBatch = apps.get_model("ocr", "OCRBatch")
    highest = 0

    for batch in OCRBatch.objects.order_by("created_at", "id").iterator():
        highest += 1
        OCRBatch.objects.filter(pk=batch.pk).update(history_number=highest)


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0019_remove_ocrnetsuitefieldmapping"),
    ]

    operations = [
        migrations.AddField(
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
        migrations.RunPython(populate_history_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="ocrbatch",
            name="history_number",
            field=models.BigIntegerField(
                db_index=True,
                editable=False,
                unique=True,
            ),
        ),
    ]
