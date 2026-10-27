from django.db import migrations, models
from django.utils import timezone


def set_existing_intervals_to_ten_minutes(apps, schema_editor):
    EmailIntegration = apps.get_model("mail_integration", "EmailIntegration")
    EmailIntegration.objects.update(sync_interval_minutes=10)
    # Make active automated connections due immediately, so the safer
    # backfill window can recover a message missed by a transient listing.
    EmailIntegration.objects.filter(
        status="CONNECTED",
        is_active=True,
        is_paused=False,
    ).update(next_sync_at=timezone.now())


class Migration(migrations.Migration):
    dependencies = [("mail_integration", "0008_emailmessage_vendor_bill_notification_sent")]

    operations = [
        migrations.AlterField(
            model_name="emailintegration",
            name="sync_interval_minutes",
            field=models.PositiveSmallIntegerField(default=10),
        ),
        migrations.RunPython(
            set_existing_intervals_to_ten_minutes,
            migrations.RunPython.noop,
        ),
    ]
