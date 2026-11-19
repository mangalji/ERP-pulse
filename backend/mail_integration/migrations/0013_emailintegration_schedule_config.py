from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("mail_integration", "0012_emailmessage_ai_extraction_duration")]

    operations = [
        migrations.AddField(
            model_name="emailintegration",
            name="schedule_config",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
