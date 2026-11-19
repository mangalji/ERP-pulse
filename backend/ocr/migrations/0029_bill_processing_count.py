from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('ocr', '0028_ocr_ai_lease_scope'),
    ]

    operations = [
        migrations.AddField(
            model_name='ocrbatch',
            name='processing_usage_counted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ocrupload',
            name='processing_usage_counted',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='ocrupload',
            name='processing_usage_pages',
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.CreateModel(
            name='BillProcessingCount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('pdf_page_limit', models.PositiveBigIntegerField(default=0)),
                ('email_bill_limit', models.PositiveBigIntegerField(default=0)),
                ('pdf_pages_consumed', models.PositiveBigIntegerField(default=0)),
                ('email_bills_consumed', models.PositiveBigIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('company', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bill_processing_count', to='tenancy.company')),
            ],
            options={'db_table': 'bill_processing_count'},
        ),
    ]
