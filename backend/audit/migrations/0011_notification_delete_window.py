from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('audit', '0010_integrationfailurealert')]

    operations = [
        migrations.AddField(
            model_name='notification',
            name='deleted_at',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
        migrations.AddField(
            model_name='notification',
            name='delete_after',
            field=models.DateTimeField(blank=True, db_index=True, null=True),
        ),
    ]
