from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0032_separate_bill_processing_periods"),
    ]

    operations = [
        migrations.AddField(
            model_name="billprocessingcount",
            name="pdf_extraction_prompt",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="billprocessingcount",
            name="email_extraction_prompt",
            field=models.TextField(blank=True, default=""),
        ),
    ]
