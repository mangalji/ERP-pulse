from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("netsuite", "0017_remove_netsuiteconnection_environment"),
    ]

    operations = [
        migrations.AddField(
            model_name="netsuiteconnection",
            name="item_catalogue_item_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="netsuiteconnection",
            name="item_catalogue_last_synced_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="netsuiteconnection",
            name="item_catalogue_sync_error",
            field=models.TextField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="netsuiteconnection",
            name="item_catalogue_sync_started_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="netsuiteconnection",
            name="item_catalogue_sync_status",
            field=models.CharField(default="idle", max_length=20),
        ),
    ]
