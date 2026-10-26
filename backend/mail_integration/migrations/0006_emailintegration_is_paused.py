from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("mail_integration", "0005_emailintegration_oauth_client_id_and_more")]

    operations = [
        migrations.AddField(
            model_name="emailintegration",
            name="is_paused",
            field=models.BooleanField(default=False),
        ),
    ]
