from django.db import migrations, models
from django.utils import timezone


def set_existing_intervals_to_one_minute(apps, schema_editor):
    EmailIntegration = apps.get_model("mail_integration", "EmailIntegration")
    EmailIntegration.objects.update(sync_interval_minutes=1)
    EmailIntegration.objects.filter(
        status="CONNECTED",
        is_active=True,
        is_paused=False,
    ).update(next_sync_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("mail_integration", "0010_emailintegration_sync_interval_five_minutes")]

    operations = [
        migrations.AlterField(
            model_name="emailintegration",
            name="sync_interval_minutes",
            field=models.PositiveSmallIntegerField(default=1),
        ),
        migrations.RunPython(
            set_existing_intervals_to_one_minute,
            migrations.RunPython.noop,
        ),
    ]
