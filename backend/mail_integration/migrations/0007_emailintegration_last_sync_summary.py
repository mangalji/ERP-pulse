from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("mail_integration", "0006_emailintegration_is_paused")]

    operations = [
        migrations.AddField(
            model_name="emailintegration",
            name="last_sync_summary",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
