from django.test import SimpleTestCase

from ocr.notebook_extraction_service import (
    FIELD_DESCRIPTIONS,
    LINE_ITEM_FIELDS,
    FIELD_DATA_TYPES,
    LINE_ITEM_DATA_TYPES,
    get_standard_field_catalog,
    resolve_field_config,
)


class OCRStandardFieldCatalogueTests(SimpleTestCase):
    def test_catalog_uses_canonical_keys(self):
        catalog = get_standard_field_catalog()

        header_keys = {
            field["key"] for field in catalog["header_fields"]
        }
        line_keys = {
            field["key"] for field in catalog["line_fields"]
        }

        self.assertEqual(
            header_keys,
            {
                "invoice_number",
                "invoice_date",
                "due_date",
                "vendor_name",
                "subsidiary",
                "currency",
                "location",
                "total_tax_amount",
                "amount",
            },
        )

        self.assertEqual(
            line_keys,
            {
                "item",
                "quantity",
                "unit_price",
                "subtotal",
                "tax_amount",
                "tax_rate",
                "total_amount",
            },
        )

    def test_catalogue_descriptions_are_strings(self):
        self.assertTrue(
            all(isinstance(value, str)
                for value in FIELD_DESCRIPTIONS.values())
        )
        self.assertTrue(
            all(isinstance(value, str)
                for value in LINE_ITEM_FIELDS.values())
        )

    def test_amount_datatypes_are_correct(self):
        self.assertEqual(FIELD_DATA_TYPES["amount"], "currency")
        self.assertEqual(
            FIELD_DATA_TYPES["total_tax_amount"], "currency"
        )
        self.assertEqual(
            LINE_ITEM_DATA_TYPES["tax_amount"], "currency"
        )
        self.assertEqual(
            LINE_ITEM_DATA_TYPES["tax_rate"], "number"
        )

    def test_removed_old_standard_keys_are_rejected(self):
        for old_key in ("description", "payment_terms"):
            with self.subTest(key=old_key):
                with self.assertRaisesRegex(
                    ValueError,
                    f"Unknown standard field '{old_key}'",
                ):
                    resolve_field_config({
                        "standard_fields": [old_key],
                        "custom_fields": [],
                    })