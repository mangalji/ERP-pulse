"""Backfill processing usage for OCR/email records created before counters."""

from django.db import migrations


def _historical_page_count(upload):
    """Return the best available page count without failing the migration."""
    # Future versions may already have persisted a document page count.
    try:
        stored = int(getattr(upload.document, 'page_count', 0) or 0)
        if stored > 0:
            return stored
    except Exception:
        pass

    extension = str(getattr(upload, 'extension', '') or '').lower().lstrip('.')
    mime_type = str(getattr(upload, 'mime_type', '') or '').lower()
    if extension != 'pdf' and mime_type != 'application/pdf':
        # Supported images/office files are admitted as one OCR page by the
        # existing adapters. This also keeps a missing historical file from
        # aborting the deployment.
        return 1

    try:
        from ocr.pdf_processor import pdf_processor
        return max(1, int(pdf_processor.get_page_count(upload.file.path)))
    except Exception:
        # A deleted/unavailable original should not prevent every company from
        # receiving its historical totals. One is the conservative fallback.
        return 1


def backfill_usage(apps, schema_editor):
    OCRBatch = apps.get_model('ocr', 'OCRBatch')
    OCRUpload = apps.get_model('ocr', 'OCRUpload')
    BillProcessingCount = apps.get_model('ocr', 'BillProcessingCount')

    # Count completed manual/file OCR only once per upload and mark it so a
    # later retry cannot charge the historical file a second time.
    uploads = OCRUpload.objects.filter(
        status='COMPLETED',
        processing_usage_counted=False,
        batch__company_id__isnull=False,
    ).select_related('batch')
    upload_totals = {}
    for upload in uploads.iterator():
        pages = _historical_page_count(upload)
        company_id = upload.batch.company_id
        upload_totals[company_id] = upload_totals.get(company_id, 0) + pages
        OCRUpload.objects.filter(pk=upload.pk).update(
            processing_usage_counted=True,
            processing_usage_pages=pages,
        )

    # A promoted vendor-bill email creates one completed EMAIL batch. There
    # is intentionally no page calculation for this source.
    email_totals = {}
    email_batches = OCRBatch.objects.filter(
        source_type='EMAIL',
        status='COMPLETED',
        processing_usage_counted=False,
        company_id__isnull=False,
    )
    for batch in email_batches.iterator():
        email_totals[batch.company_id] = email_totals.get(batch.company_id, 0) + 1
        OCRBatch.objects.filter(pk=batch.pk).update(processing_usage_counted=True)

    company_ids = set(upload_totals) | set(email_totals)
    for company_id in company_ids:
        usage, _ = BillProcessingCount.objects.get_or_create(company_id=company_id)
        # Add only rows that were not already counted by the live tracker. A
        # SuperAdmin's limits and any newer consumption remain untouched.
        usage.pdf_pages_consumed += upload_totals.get(company_id, 0)
        usage.email_bills_consumed += email_totals.get(company_id, 0)
        usage.save(update_fields=['pdf_pages_consumed', 'email_bills_consumed', 'updated_at'])


class Migration(migrations.Migration):
    dependencies = [
        ('ocr', '0029_bill_processing_count'),
    ]

    operations = [migrations.RunPython(backfill_usage, migrations.RunPython.noop)]
