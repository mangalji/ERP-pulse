from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("netsuite", "0016_remove_legacy_user_active_connection_index"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="netsuiteconnection",
            name="environment",
        ),
    ]
