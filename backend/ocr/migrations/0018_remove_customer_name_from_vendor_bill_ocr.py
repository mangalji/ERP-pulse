"""Remove Customer Name from Vendor Bill OCR data and templates.

Existing JSON snapshots/configurations are cleaned before dropping the legacy
structured column. This intentionally removes the obsolete Customer Name data
from historical OCR payloads and template selections.
"""

import re

from django.db import migrations


def _slug(value):
    if not isinstance(value, str):
        return ""
    return re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")


def _remove_customer_name_key(value):
    if isinstance(value, dict):
        return {
            key: _remove_customer_name_key(item)
            for key, item in value.items()
            if _slug(str(key)) != "customer_name"
        }
    if isinstance(value, list):
        return [_remove_customer_name_key(item) for item in value]
    return value


def _clean_config(config):
    if not isinstance(config, dict):
        return config

    cleaned = dict(config)
    for list_key in ("standard_fields", "disabled_standard_fields"):
        values = cleaned.get(list_key)
        if isinstance(values, list):
            cleaned[list_key] = [value for value in values if _slug(value) != "customer_name"]

    overrides = cleaned.get("standard_field_overrides")
    if isinstance(overrides, dict):
        cleaned["standard_field_overrides"] = {
            key: value for key, value in overrides.items()
            if _slug(str(key)) != "customer_name"
        }

    for list_key in ("custom_fields", "disabled_custom_fields"):
        values = cleaned.get(list_key)
        if isinstance(values, list):
            cleaned_values = []
            for value in values:
                if isinstance(value, dict):
                    field_key = _slug(str(value.get("key") or ""))
                    field_label = _slug(str(value.get("label") or ""))
                    if field_key == "customer_name" or field_label == "customer_name":
                        continue
                elif _slug(value) == "customer_name":
                    continue
                cleaned_values.append(value)
            cleaned[list_key] = cleaned_values

    return cleaned


def remove_legacy_customer_name(apps, schema_editor):
    alias = schema_editor.connection.alias
    OCRDocumentVersion = apps.get_model("ocr", "OCRDocumentVersion")
    OCRUpload = apps.get_model("ocr", "OCRUpload")
    OCRBatch = apps.get_model("ocr", "OCRBatch")
    OCRExtractionTemplate = apps.get_model("ocr", "OCRExtractionTemplate")

    for version in OCRDocumentVersion.objects.using(alias).all().iterator():
        updates = {}
        for field in ("raw_ocr", "normalized_json", "reviewed_json"):
            old_value = getattr(version, field)
            new_value = _remove_customer_name_key(old_value)
            if new_value != old_value:
                updates[field] = new_value
        if updates:
            OCRDocumentVersion.objects.using(alias).filter(pk=version.pk).update(**updates)

    for upload in OCRUpload.objects.using(alias).all().iterator():
        old_value = upload.live_result_json
        new_value = _remove_customer_name_key(old_value)
        if new_value != old_value:
            OCRUpload.objects.using(alias).filter(pk=upload.pk).update(live_result_json=new_value)

    for batch in OCRBatch.objects.using(alias).all().iterator():
        old_value = batch.requested_fields_json
        new_value = _clean_config(old_value)
        if new_value != old_value:
            OCRBatch.objects.using(alias).filter(pk=batch.pk).update(requested_fields_json=new_value)

    for template in OCRExtractionTemplate.objects.using(alias).all().iterator():
        old_value = template.fields_config
        new_value = _clean_config(old_value)
        if new_value != old_value:
            OCRExtractionTemplate.objects.using(alias).filter(pk=template.pk).update(fields_config=new_value)


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0017_ocr_storage_adapter"),
    ]

    operations = [
        migrations.RunPython(remove_legacy_customer_name),
        migrations.RemoveField(
            model_name="ocrdocumentversion",
            name="customer_name",
        ),
    ]