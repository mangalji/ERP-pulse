from django.db import migrations, models
from django.utils import timezone


def set_existing_intervals_to_five_minutes(apps, schema_editor):
    EmailIntegration = apps.get_model("mail_integration", "EmailIntegration")
    EmailIntegration.objects.update(sync_interval_minutes=5)
    # Prompt the new cadence to start without waiting for an old 10-minute
    # schedule, while the sync service still protects against duplicates.
    EmailIntegration.objects.filter(
        status="CONNECTED",
        is_active=True,
        is_paused=False,
    ).update(next_sync_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("mail_integration", "0009_emailintegration_sync_interval_ten_minutes")]

    operations = [
        migrations.AlterField(
            model_name="emailintegration",
            name="sync_interval_minutes",
            field=models.PositiveSmallIntegerField(default=5),
        ),
        migrations.RunPython(
            set_existing_intervals_to_five_minutes,
            migrations.RunPython.noop,
        ),
    ]
