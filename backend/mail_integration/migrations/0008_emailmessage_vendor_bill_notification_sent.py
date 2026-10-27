from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("mail_integration", "0007_emailintegration_last_sync_summary")]

    operations = [
        migrations.AddField(
            model_name="emailmessage",
            name="vendor_bill_notification_sent",
            field=models.BooleanField(default=False),
        ),
    ]
