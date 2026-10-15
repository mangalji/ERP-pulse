"""Retire the old per-connection OCR -> NetSuite mapping table.

Saved OCRExtractionTemplate.fields_config is now the mapping source of truth.
OCRBatch.requested_fields_json is the immutable per-upload snapshot used by
extraction, validation and posting. NetSuiteFieldCatalogue remains target-schema
metadata only. The obsolete table is renamed to a legacy archive rather than
being dropped, so old rows cannot affect runtime but remain recoverable for audit.
"""

from django.db import migrations


LEGACY_TABLE = "ocr_netsuite_field_mapping"
ARCHIVE_TABLE = "ocr_netsuite_field_mapping_legacy"


def _rename_if_needed(schema_editor, source_table, target_table):
    connection = schema_editor.connection
    with connection.cursor() as cursor:
        tables = set(connection.introspection.table_names(cursor))
        if source_table not in tables:
            # Also tolerate a database where the old table was already removed
            # or archived manually. The Django migration state is still retired.
            return
        if target_table in tables:
            raise RuntimeError(
                f"Cannot rename {source_table}: {target_table} already exists. "
                "Resolve the duplicate legacy table manually before migrating."
            )
        cursor.execute(
            "ALTER TABLE "
            f"{schema_editor.quote_name(source_table)} "
            "RENAME TO "
            f"{schema_editor.quote_name(target_table)}"
        )


def archive_legacy_table(apps, schema_editor):
    _rename_if_needed(schema_editor, LEGACY_TABLE, ARCHIVE_TABLE)


def restore_legacy_table(apps, schema_editor):
    _rename_if_needed(schema_editor, ARCHIVE_TABLE, LEGACY_TABLE)


class Migration(migrations.Migration):
    dependencies = [
        ("ocr", "0018_remove_customer_name_from_vendor_bill_ocr"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(archive_legacy_table, restore_legacy_table),
            ],
            state_operations=[
                migrations.DeleteModel(name="OCRNetSuiteFieldMapping"),
            ],
        ),
    ]