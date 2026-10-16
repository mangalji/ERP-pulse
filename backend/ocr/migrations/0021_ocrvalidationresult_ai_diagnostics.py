from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0020_ocrbatch_history_number"),
    ]

    operations = [
        migrations.AddField(
            model_name="ocrvalidationresult",
            name="ai_diagnostics",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
