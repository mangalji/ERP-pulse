import ocr.storage
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('ocr', '0016_ocrupload_job_lease_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='OCRStoredFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255, unique=True)),
                ('content', models.BinaryField()),
                ('size', models.BigIntegerField(default=0)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'db_table': 'ocr_stored_file',
            },
        ),
        migrations.AlterField(
            model_name='ocrdocumentversion',
            name='original_document',
            field=models.FileField(blank=True, null=True, storage=ocr.storage.ocr_file_storage, upload_to='ocr/versions/original/'),
        ),
        migrations.AlterField(
            model_name='ocrdocumentversion',
            name='processed_document',
            field=models.FileField(blank=True, null=True, storage=ocr.storage.ocr_file_storage, upload_to='ocr/versions/processed/'),
        ),
        migrations.AlterField(
            model_name='ocrupload',
            name='file',
            field=models.FileField(storage=ocr.storage.ocr_file_storage, upload_to='ocr/'),
        ),
    ]