from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0033_bill_processing_prompts"),
    ]

    operations = [
        migrations.AlterField(
            model_name="ocrupload",
            name="status",
            field=models.CharField(
                choices=[
                    ("UPLOADED", "Uploaded"),
                    ("PROCESSING", "Processing"),
                    ("RETRYING", "Retrying"),
                    ("COMPLETED", "Completed"),
                    ("FAILED", "Failed"),
                ],
                db_index=True,
                default="UPLOADED",
                max_length=20,
            ),
        ),
    ]
