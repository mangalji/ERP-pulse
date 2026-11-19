from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('ocr', '0030_backfill_bill_processing_usage'),
    ]

    operations = [
        migrations.AddField(
            model_name='billprocessingcount',
            name='allocation_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='billprocessingcount',
            name='allocation_end_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
