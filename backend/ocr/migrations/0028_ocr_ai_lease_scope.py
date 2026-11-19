from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("ocr", "0027_ai_extraction_duration"),
    ]

    operations = [
        migrations.RenameModel(
            old_name="OCRGeminiLease",
            new_name="OCRAILimitLease",
        ),
        migrations.AlterModelTable(
            name="ocrailimitlease",
            table="ocr_ai_limit_lease",
        ),
        migrations.AddField(
            model_name="ocrailimitlease",
            name="scope_key",
            field=models.CharField(db_index=True, default="legacy-global", max_length=64),
            preserve_default=False,
        ),
        migrations.AddIndex(
            model_name="ocrailimitlease",
            index=models.Index(
                fields=["scope_key", "lease_expires_at"],
                name="ocr_ai_lease_scope_active_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="ocrailimitlease",
            index=models.Index(
                fields=["scope_key", "created_at"],
                name="ocr_ai_lease_scope_recent_idx",
            ),
        ),
        migrations.CreateModel(
            name="OCRExtractionPart",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("part_number", models.PositiveIntegerField()),
                ("page_start", models.PositiveIntegerField()),
                ("page_end", models.PositiveIntegerField()),
                ("status", models.CharField(choices=[("PENDING", "Pending"), ("PROCESSING", "Processing"), ("COMPLETED", "Completed"), ("FAILED", "Failed")], db_index=True, default="PENDING", max_length=16)),
                ("result_json", models.JSONField(blank=True, null=True)),
                ("error", models.TextField(blank=True, default="")),
                ("attempt_count", models.PositiveSmallIntegerField(default=0)),
                ("started_at", models.DateTimeField(blank=True, null=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("upload", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="extraction_parts", to="ocr.ocrupload")),
            ],
            options={"db_table": "ocr_extraction_part"},
        ),
        migrations.AddConstraint(
            model_name="ocrextractionpart",
            constraint=models.UniqueConstraint(fields=("upload", "part_number"), name="ocr_part_upload_number_unique"),
        ),
        migrations.AddIndex(
            model_name="ocrextractionpart",
            index=models.Index(fields=["upload", "status"], name="ocr_part_upload_status_idx"),
        ),
        migrations.AddField(
            model_name="ocrupload",
            name="retry_count",
            field=models.PositiveSmallIntegerField(default=0),
        ),
    ]
