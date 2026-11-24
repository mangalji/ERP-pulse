from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mail_integration", "0014_alter_emailintegration_sync_interval_minutes"),
    ]

    operations = [
        migrations.AddField(
            model_name="emailintegration",
            name="latest_fetched_email_received_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AlterField(
            model_name="emailintegration",
            name="provider",
            field=models.CharField(
                choices=[
                    ("GOOGLE", "Google Gmail"),
                    ("ZOHO", "Zoho Mail"),
                    ("OUTLOOK", "Microsoft Outlook"),
                ],
                max_length=20,
            ),
        ),
    ]
