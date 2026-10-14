from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("netsuite", "0015_netsuitebatchjob"),
    ]

    operations = [
        migrations.RemoveIndex(
            model_name="netsuiteconnection",
            name="netsuite_conn_user_active_idx",
        ),
    ]