from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("mail_integration", "0011_emailintegration_sync_interval_one_minute"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailmessage",
            name="ai_extraction_duration_ms",
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
