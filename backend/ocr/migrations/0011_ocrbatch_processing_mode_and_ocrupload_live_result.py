from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("ocr", "0010_remove_ocrlineitem_ocr_line_item_version_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="ocrbatch",
            name="processing_mode",
            field=models.CharField(
                choices=[
                    ("SINGLE", "Single"),
                    ("MULTIPLE", "Multiple"),
                ],
                db_index=True,
                default="MULTIPLE",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="ocrupload",
            name="live_result_json",
            field=models.JSONField(
                blank=True,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="ocrupload",
            name="live_result_expires_at",
            field=models.DateTimeField(
                blank=True,
                db_index=True,
                null=True,
            ),
        ),
    ]