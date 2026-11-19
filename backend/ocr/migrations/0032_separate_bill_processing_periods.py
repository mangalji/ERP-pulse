from django.db import migrations, models


def copy_common_periods(apps, schema_editor):
    Usage = apps.get_model('ocr', 'BillProcessingCount')
    for usage in Usage.objects.all().iterator():
        usage.pdf_allocation_start_date = usage.allocation_start_date
        usage.pdf_allocation_end_date = usage.allocation_end_date
        usage.email_allocation_start_date = usage.allocation_start_date
        usage.email_allocation_end_date = usage.allocation_end_date
        usage.save(update_fields=[
            'pdf_allocation_start_date', 'pdf_allocation_end_date',
            'email_allocation_start_date', 'email_allocation_end_date',
        ])


class Migration(migrations.Migration):
    dependencies = [
        ('ocr', '0031_bill_processing_count_dates'),
    ]

    operations = [
        migrations.AddField(
            model_name='billprocessingcount',
            name='pdf_allocation_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='billprocessingcount',
            name='pdf_allocation_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='billprocessingcount',
            name='email_allocation_start_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='billprocessingcount',
            name='email_allocation_end_date',
            field=models.DateField(blank=True, null=True),
        ),
        migrations.RunPython(copy_common_periods, migrations.RunPython.noop),
        migrations.RemoveField(model_name='billprocessingcount', name='allocation_start_date'),
        migrations.RemoveField(model_name='billprocessingcount', name='allocation_end_date'),
    ]
