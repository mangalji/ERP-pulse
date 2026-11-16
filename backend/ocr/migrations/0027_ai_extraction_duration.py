from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0026_history_number_after_validation"),
    ]

    operations = [
        migrations.AddField(
            model_name="ocrupload",
            name="ai_extraction_duration_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="ocrdocument",
            name="ai_extraction_duration_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
