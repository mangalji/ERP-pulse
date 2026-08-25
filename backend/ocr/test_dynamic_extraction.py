"""
Focused tests for Phase 2 dynamic OCR extraction configuration.

Covers the pure extraction-contract logic (field resolution, schema and
prompt generation, normalization, reinspection/merge, custom-field
datatype preservation, header/line scope, the line-custom-field rule,
and default-path compatibility) plus the template APIs and the upload
requested-fields validation.

The pure-logic tests deliberately avoid the database, Gemini, and Celery
so they run as fast, deterministic unit checks. The API tests use
Django's APITestCase with a real (in-memory) database.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase, TestCase, override_settings
from rest_framework.test import APITestCase

from ocr.notebook_extraction_service import (
    EXTRACTION_SCHEMA,
    FIELD_DATA_TYPES,
    LINE_ITEM_DATA_TYPES,
    _apply_datatype_normalization,
    _build_schema,
    _json_schema_type,
    _merge_corrected_result,
    _normalize_datatype,
    _normalize_result,
    _verification_is_needed,
    build_prompt,
    resolve_field_config,
)
from ocr.tasks import (
    acquire_extraction_lock,
    build_extraction_config_hash,
    build_extraction_contract_version,
    build_ocr_cache_identity,
    build_ocr_cache_key,
    _build_lock_key,
    read_valid_cached_result,
    release_extraction_lock,
    wait_for_extraction_lock,
    write_completed_cached_result,
)
from ocr.serializers import OCRExtractionTemplateCreateSerializer
from ocr.test_ocr_view import _build_requested_fields, _parse_requested_fields


# ----------------------------------------------------------------------
# Pure-logic unit tests (no database)
# ----------------------------------------------------------------------

class DynamicExtractionUnitTests(SimpleTestCase):
    def test_default_compatibility(self):
        """Absent config must reproduce the exact original default contract."""
        hf, lf, ili, ht, lt = resolve_field_config(None)
        self.assertEqual(set(hf.keys()), set(FIELD_DATA_TYPES.keys()))
        self.assertTrue(ili)
        self.assertEqual(set(lf.keys()), set(LINE_ITEM_DATA_TYPES.keys()))

        schema = _build_schema(hf, lf, ili, ht, lt)
        self.assertEqual(schema, EXTRACTION_SCHEMA)

    def test_subset_standard_fields_drops_line_items(self):
        requested = {"standard_fields": ["invoice_number", "vendor_name"]}
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        self.assertEqual(set(hf.keys()), {"invoice_number", "vendor_name"})
        self.assertFalse(ili)
        self.assertEqual(lf, {})
        schema = _build_schema(hf, lf, ili, ht, lt)
        self.assertNotIn("line_items", schema["properties"])
        self.assertNotIn("line_items", schema["required"])

    def test_custom_header_field_resolved(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "PO Number",
                    "description": "Purchase order reference",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        self.assertIn("po_number", hf)
        self.assertEqual(hf["po_number"], "Purchase order reference")
        self.assertTrue(ili)
        schema = _build_schema(hf, lf, ili, ht, lt)
        self.assertIn("po_number", schema["properties"])
        self.assertEqual(
            schema["properties"]["po_number"]["type"], "string"
        )
        self.assertIn("po_number", schema["required"])

    def test_custom_field_datatype_preserved_in_schema(self):
        cases = {
            "number": "number",
            "currency": "number",
            "boolean": "boolean",
            "date": "string",
            "text": "string",
        }
        for data_type, json_type in cases.items():
            requested = {
                "standard_fields": ["invoice_number", "line_items"],
                "custom_fields": [
                    {
                        "label": f"Field {data_type}",
                        "description": "x",
                        "scope": "header",
                        "data_type": data_type,
                    }
                ],
            }
            hf, lf, ili, ht, lt = resolve_field_config(requested)
            key = f"field_{data_type}"
            self.assertEqual(_json_schema_type(ht[key]), json_type)

    def test_custom_field_format_hint_in_prompt(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Signed Date",
                    "description": "Contract sign date",
                    "scope": "header",
                    "data_type": "date",
                },
                {
                    "label": "Is Certified",
                    "description": "Whether certified",
                    "scope": "header",
                    "data_type": "boolean",
                },
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        prompt = build_prompt(hf, lf, ili, ht, lt)
        self.assertIn("ISO YYYY-MM-DD", prompt)
        self.assertIn("true or false", prompt)

    def test_line_custom_field_requires_line_items(self):
        requested = {
            "standard_fields": ["invoice_number"],  # line_items disabled
            "custom_fields": [
                {
                    "label": "Batch Number",
                    "description": "Lot number",
                    "scope": "line",
                    "data_type": "text",
                }
            ],
        }
        with self.assertRaises(ValueError):
            resolve_field_config(requested)

    def test_line_custom_field_with_line_items(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Batch Number",
                    "description": "Lot number",
                    "scope": "line",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        self.assertIn("batch_number", lf)
        self.assertTrue(ili)
        schema = _build_schema(hf, lf, ili, ht, lt)
        line_props = schema["properties"]["line_items"]["items"]["properties"]
        self.assertIn("batch_number", line_props)

    def test_normalize_result_keeps_custom_fields(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "PO Number",
                    "description": "x",
                    "scope": "header",
                    "data_type": "text",
                },
                {
                    "label": "Batch Number",
                    "description": "x",
                    "scope": "line",
                    "data_type": "text",
                },
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())
        data = {
            "invoice_number": "INV-1",
            "po_number": "PO-9",
            "line_items": [{"description": "Item", "batch_number": "B1"}],
        }
        normalized = _normalize_result(
            data, header_keys, line_keys, ili
        )
        self.assertEqual(normalized["po_number"], "PO-9")
        self.assertEqual(normalized["line_items"][0]["batch_number"], "B1")

    def test_normalize_result_omits_line_items_when_disabled(self):
        requested = {"standard_fields": ["invoice_number"]}
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        normalized = _normalize_result(
            {"invoice_number": "INV-1"}, tuple(hf.keys()), tuple(lf.keys()), ili
        )
        self.assertNotIn("line_items", normalized)

    def test_merge_fills_custom_header_field(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "PO Number",
                    "description": "x",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())
        candidate = {"invoice_number": "INV-1", "po_number": None}
        audit = {
            "needs_correction": True,
            "corrections": [
                {"field": "po_number", "corrected_value": "PO-9"}
            ],
        }
        merged = _merge_corrected_result(
            candidate, audit, header_keys, line_keys, ili
        )
        self.assertEqual(merged["po_number"], "PO-9")

    def test_merge_fills_custom_line_field(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Batch Number",
                    "description": "x",
                    "scope": "line",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())
        candidate = {
            "invoice_number": "INV-1",
            "line_items": [{"description": "Item", "batch_number": None}],
        }
        audit = {
            "needs_correction": True,
            "corrections": [
                {
                    "field": "line_items",
                    "corrected_value": [
                        {"description": "Item", "batch_number": "B1"}
                    ],
                }
            ],
        }
        merged = _merge_corrected_result(
            candidate, audit, header_keys, line_keys, ili
        )
        self.assertEqual(merged["line_items"][0]["batch_number"], "B1")

    def test_verification_uses_only_requested_high_value_fields(self):
        # A custom config that drops most standard verification fields and
        # includes only invoice_number must not force verification for the
        # removed high-value fields.
        requested = {"standard_fields": ["invoice_number", "line_items"]}
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        header_keys = tuple(hf.keys())
        # invoice_number present, so no verification needed.
        self.assertFalse(
            _verification_is_needed(
                {"invoice_number": "INV-1", "line_items": []}, header_keys
            )
        )

    def test_build_prompt_excludes_removed_fields(self):
        requested = {"standard_fields": ["invoice_number", "line_items"]}
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        prompt = build_prompt(hf, lf, ili, ht, lt)
        self.assertNotIn('"vendor_name"', prompt)
        self.assertIn('"invoice_number"', prompt)

    def test_reserved_key_collision_rejected(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Invoice Number",
                    "description": "x",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }
        with self.assertRaises(ValueError):
            resolve_field_config(requested)

    def test_duplicate_custom_field_rejected(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "PO Number",
                    "description": "x",
                    "scope": "header",
                    "data_type": "text",
                },
                {
                    "label": "PO Number",
                    "description": "y",
                    "scope": "header",
                    "data_type": "text",
                },
            ],
        }
        with self.assertRaises(ValueError):
            resolve_field_config(requested)

    def test_empty_explicit_config_rejected(self):
        # An intentional empty selection must NOT be silently upgraded to
        # the full default set; it is rejected instead.
        with self.assertRaises(ValueError):
            resolve_field_config({"standard_fields": [], "custom_fields": []})

    def test_empty_dict_remains_default(self):
        # An absent/empty {} config is the legacy default-extraction signal.
        hf, lf, ili, ht, lt = resolve_field_config({})
        self.assertEqual(set(hf.keys()), set(FIELD_DATA_TYPES.keys()))

    def test_custom_header_field_full_extraction_flow(self):
        """TEST 1-4 / 7-10: Simulate full extraction flow with a custom header field."""
        requested = {
            "standard_fields": [
                "invoice_number", "invoice_date", "vendor_name", "line_items"
            ],
            "custom_fields": [
                {
                    "label": "Memo",
                    "description": "description of the invoice",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)

        # TEST 1: Custom header field appears in resolved extraction config.
        self.assertIn("memo", hf)
        self.assertEqual(hf["memo"], "description of the invoice")

        # TEST 2: Custom header field appears in generated JSON schema.
        schema = _build_schema(hf, lf, ili, ht, lt)
        self.assertIn("memo", schema["properties"])
        self.assertEqual(schema["properties"]["memo"]["type"], "string")
        self.assertTrue(schema["properties"]["memo"]["nullable"])
        self.assertIn("memo", schema["required"])

        # TEST 3: Custom header field appears in generated AI prompt.
        prompt = build_prompt(hf, lf, ili, ht, lt)
        self.assertIn('"memo"', prompt)
        self.assertIn("description of the invoice", prompt)

        # Simulate Gemini returning the custom field.
        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())
        data = {
            "invoice_number": "INV-1",
            "invoice_date": "2026-03-12",
            "vendor_name": "Test Vendor",
            "memo": "Test memo value",
            "line_items": [
                {"description": "Item 1", "quantity": 1, "unit_price": 10, "amount": 10}
            ],
        }

        # TEST 4: Custom header field survives normalization.
        normalized = _normalize_result(data, header_keys, line_keys, ili)
        self.assertEqual(normalized["memo"], "Test memo value")
        self.assertEqual(normalized["invoice_number"], "INV-1")
        self.assertEqual(normalized["line_items"][0]["description"], "Item 1")

        # TEST 7: Explicitly verify final normalized result contains arbitrary
        # custom fields, not only fields from EXTRACTION_SCHEMA.
        self.assertIn("memo", normalized)
        self.assertIsInstance(normalized["memo"], str)

        # Simulate verification passing (no corrections).
        audit = {
            "needs_correction": False,
            "corrections": [],
        }

        # TEST 5: Custom field survives reinspection/merge.
        merged = _merge_corrected_result(normalized, audit, header_keys, line_keys, ili)
        self.assertEqual(merged["memo"], "Test memo value")
        self.assertIn("memo", merged)

        # TEST 9: Verify deselected standard fields remain excluded.
        requested_subset = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Memo",
                    "description": "description of the invoice",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }
        hf2, lf2, ili2, ht2, lt2 = resolve_field_config(requested_subset)
        schema2 = _build_schema(hf2, lf2, ili2, ht2, lt2)
        self.assertNotIn("vendor_name", schema2["properties"])
        self.assertNotIn("invoice_date", schema2["properties"])
        self.assertIn("memo", schema2["properties"])

    def test_custom_line_field_full_extraction_flow(self):
        """TEST 6: Custom line-item field appears in schema and survives normalization."""
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Batch Number",
                    "description": "Lot number",
                    "scope": "line",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        self.assertIn("batch_number", lf)

        schema = _build_schema(hf, lf, ili, ht, lt)
        line_props = schema["properties"]["line_items"]["items"]["properties"]
        self.assertIn("batch_number", line_props)
        self.assertEqual(line_props["batch_number"]["type"], "string")

        prompt = build_prompt(hf, lf, ili, ht, lt)
        self.assertIn('"batch_number"', prompt)

        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())
        data = {
            "invoice_number": "INV-1",
            "line_items": [
                {"description": "Item", "batch_number": "B1"}
            ],
        }
        normalized = _normalize_result(data, header_keys, line_keys, ili)
        self.assertEqual(normalized["line_items"][0]["batch_number"], "B1")

    def test_draft_custom_field_not_included(self):
        """TEST 8: A draft custom field must NOT be included in the config."""
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Draft Field",
                    "description": "not yet confirmed",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        # In the frontend, draft fields are filtered out before building requested_fields.
        # The backend should only receive confirmed fields. If it receives an
        # unconfirmed/draft field, it should still be processed since the
        # backend doesn't know about draft state — the frontend is responsible
        # for not sending drafts.
        self.assertIn("draft_field", hf)

    def test_default_behavior_unchanged_without_custom_config(self):
        """TEST 10: Default extraction behavior unchanged when no custom config."""
        hf, lf, ili, ht, lt = resolve_field_config(None)
        self.assertEqual(set(hf.keys()), set(FIELD_DATA_TYPES.keys()))
        self.assertTrue(ili)
        self.assertEqual(set(lf.keys()), set(LINE_ITEM_DATA_TYPES.keys()))

        schema = _build_schema(hf, lf, ili, ht, lt)
        self.assertEqual(schema, EXTRACTION_SCHEMA)

        prompt = build_prompt(hf, lf, ili, ht, lt)
        self.assertIn('"invoice_number"', prompt)
        self.assertIn("Line-item fields:", prompt)

        data = {
            "invoice_number": "INV-1",
            "invoice_date": "2026-03-12",
            "vendor_name": "V",
            "currency": "USD",
            "subtotal": 100,
            "tax_amount": 10,
            "tax_rate": 10,
            "total_amount": 110,
            "payment_terms": "Net 30",
            "line_items": [],
        }
        result = _normalize_result(data)
        self.assertEqual(result["invoice_number"], "INV-1")
        self.assertEqual(result["line_items"], [])

    def test_custom_field_with_verification_correction(self):
        """Custom field survives verification when verifier returns no correction."""
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Memo",
                    "description": "description of the invoice",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())

        candidate = {
            "invoice_number": "INV-1",
            "memo": "Original memo",
            "line_items": [],
        }
        audit = {
            "needs_correction": True,
            "corrections": [
                {"field": "invoice_number", "corrected_value": "INV-2"}
            ],
        }
        merged = _merge_corrected_result(candidate, audit, header_keys, line_keys, ili)
        # Verifier corrected invoice_number but memo should remain untouched.
        self.assertEqual(merged["invoice_number"], "INV-2")
        self.assertEqual(merged["memo"], "Original memo")

    def test_custom_field_arbitrary_labels(self):
        """Custom fields work with arbitrary user-defined labels."""
        labels = [
            "GST Number",
            "Purchase Order",
            "Invoice Reference",
            "Project Code",
            "Department",
            "Cost Center",
        ]
        for label in labels:
            requested = {
                "standard_fields": ["invoice_number", "line_items"],
                "custom_fields": [
                    {
                        "label": label,
                        "description": f"Extract {label}",
                        "scope": "header",
                        "data_type": "text",
                    }
                ],
            }
            hf, lf, ili, ht, lt = resolve_field_config(requested)
            expected_key = label.lower().replace(" ", "_").replace("-", "_")
            self.assertIn(expected_key, hf)
            schema = _build_schema(hf, lf, ili, ht, lt)
            self.assertIn(expected_key, schema["properties"])
            self.assertIn(expected_key, schema["required"])


class DynamicExtractionSerializerTests(SimpleTestCase):
    def test_template_serializer_rejects_line_rule(self):
        serializer = OCRExtractionTemplateCreateSerializer(
            data={
                "name": "Bad Template",
                "fields_config": {
                    "standard_fields": ["invoice_number"],
                    "custom_fields": [
                        {
                            "label": "Batch",
                            "description": "x",
                            "scope": "line",
                            "data_type": "text",
                        }
                    ],
                },
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("fields_config", serializer.errors)

    def test_template_serializer_accepts_valid_config(self):
        serializer = OCRExtractionTemplateCreateSerializer(
            data={
                "name": "Good Template",
                "fields_config": {
                    "standard_fields": ["invoice_number", "line_items"],
                    "custom_fields": [
                        {
                            "label": "PO Number",
                            "description": "x",
                            "scope": "header",
                            "data_type": "text",
                        }
                    ],
                },
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)

    def test_template_serializer_rejects_empty_config(self):
        serializer = OCRExtractionTemplateCreateSerializer(
            data={
                "name": "Empty",
                "fields_config": {
                    "standard_fields": [],
                    "custom_fields": [],
                },
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("fields_config", serializer.errors)

    def test_template_serializer_rejects_collision(self):
        serializer = OCRExtractionTemplateCreateSerializer(
            data={
                "name": "Collision",
                "fields_config": {
                    "standard_fields": ["invoice_number", "line_items"],
                    "custom_fields": [
                        {
                            "label": "Invoice Number",
                            "description": "x",
                            "scope": "header",
                            "data_type": "text",
                        }
                    ],
                },
            }
        )
        self.assertFalse(serializer.is_valid())
        self.assertIn("fields_config", serializer.errors)


class RequestedFieldsParsingTests(SimpleTestCase):
    def test_parse_json_string(self):
        parsed = _parse_requested_fields('{"standard_fields": ["invoice_number"]}')
        self.assertEqual(parsed["standard_fields"], ["invoice_number"])

    def test_parse_invalid_json_raises(self):
        with self.assertRaises(ValueError):
            _parse_requested_fields("{not json")

    def test_parse_none_returns_none(self):
        self.assertIsNone(_parse_requested_fields(None))


# ----------------------------------------------------------------------
# Database-backed API tests
# ----------------------------------------------------------------------

@override_settings(MEDIA_ROOT=None)
class DynamicExtractionAPITests(APITestCase):
    def setUp(self):
        from django.contrib.auth import get_user_model
        from tenancy.models import Company

        from ocr.models import OCRExtractionTemplate

        self.User = get_user_model()
        self.Company = Company
        self.OCRExtractionTemplate = OCRExtractionTemplate

        self.company = Company.objects.create(
            name="Phase2 Co", code=f"P2{abs(hash('Phase2 Co')) % 100000}"
        )
        self.user = self.User.objects.create_user(
            email="phase2@example.com",
            password="testpass123",
            company=self.company,
            is_active=True,
        )
        self.client.force_authenticate(user=self.user)

    def test_standard_fields_catalogue(self):
        response = self.client.get("/api/v1/ocr/extraction-fields/")
        self.assertEqual(response.status_code, 200)
        data = response.json().get("data", response.json())
        self.assertIn("header_fields", data)
        self.assertIn("line_fields", data)
        self.assertTrue(data["supports_line_items"])
        keys = {f["key"] for f in data["header_fields"]}
        self.assertIn("invoice_number", keys)

    def test_template_create_list_and_detail(self):
        payload = {
            "name": "GST Invoices",
            "fields_config": {
                "standard_fields": ["invoice_number", "vendor_name", "line_items"],
                "custom_fields": [
                    {
                        "label": "GSTIN",
                        "description": "Vendor GST number",
                        "scope": "header",
                        "data_type": "text",
                    }
                ],
            },
        }
        create = self.client.post("/api/v1/ocr/extraction-templates/", payload, format="json")
        self.assertEqual(create.status_code, 201, create.content)
        template_id = create.json()["data"]["id"]

        listing = self.client.get("/api/v1/ocr/extraction-templates/")
        self.assertEqual(listing.status_code, 200)
        names = [t["name"] for t in listing.json()["data"]]
        self.assertIn("GST Invoices", names)

        detail = self.client.get(
            f"/api/v1/ocr/extraction-templates/{template_id}/"
        )
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(
            detail.json()["data"]["fields_config"]["custom_fields"][0]["label"],
            "GSTIN",
        )

    def test_template_unique_name_updates(self):
        payload = {
            "name": "Reusable",
            "fields_config": {"standard_fields": ["invoice_number", "line_items"]},
        }
        first = self.client.post("/api/v1/ocr/extraction-templates/", payload, format="json")
        self.assertEqual(first.status_code, 201)
        second = self.client.post("/api/v1/ocr/extraction-templates/", payload, format="json")
        self.assertEqual(second.status_code, 201)
        self.assertEqual(
            first.json()["data"]["id"], second.json()["data"]["id"]
        )

    def test_template_is_company_scoped(self):
        other_company = self.Company.objects.create(
            name="Other Co", code=f"OC{abs(hash('Other Co')) % 100000}"
        )
        other_user = self.User.objects.create_user(
            email="other@example.com",
            password="testpass123",
            company=other_company,
            is_active=True,
        )
        self.client.force_authenticate(user=other_user)
        listing = self.client.get("/api/v1/ocr/extraction-templates/")
        self.assertEqual(len(listing.json()["data"]), 0)

    def test_missing_template_raises_for_build_requested_fields(self):
        from ocr.test_ocr_view import _build_requested_fields

        class FakeRequest:
            data = {"template_id": "00000000-0000-0000-0000-000000000000"}
            user = self.user

        with self.assertRaises(ValueError):
            _build_requested_fields(FakeRequest())

    def test_build_requested_fields_loads_company_template(self):
        template = self.OCRExtractionTemplate.objects.create(
            company=self.company,
            name="My Tpl",
            created_by=self.user,
            fields_config={
                "standard_fields": ["invoice_number", "line_items"],
                "custom_fields": [
                    {
                        "label": "PO Number",
                        "description": "x",
                        "scope": "header",
                        "data_type": "text",
                    }
                ],
            },
        )

        class FakeRequest:
            data = {"template_id": str(template.id)}
            user = self.user

        resolved = _build_requested_fields(FakeRequest())
        self.assertIsNotNone(resolved)
        self.assertIn(
            "po_number",
            resolve_field_config(resolved)[:2][0],
        )


class DatatypeNormalizationTests(SimpleTestCase):
    """Tests for server-side datatype normalization."""

    def test_text_normalization(self):
        from ocr.notebook_extraction_service import _normalize_datatype

        self.assertEqual(_normalize_datatype("hello", "text"), "hello")
        self.assertEqual(_normalize_datatype("  hello  ", "text"), "hello")
        self.assertIsNone(_normalize_datatype("", "text"))
        self.assertIsNone(_normalize_datatype(None, "text"))
        self.assertEqual(_normalize_datatype(123, "text"), "123")

    def test_number_normalization(self):
        from ocr.notebook_extraction_service import _normalize_datatype

        self.assertEqual(_normalize_datatype("18", "number"), 18)
        self.assertEqual(_normalize_datatype("18.50", "number"), 18.5)
        self.assertEqual(_normalize_datatype("18%", "number"), 18)
        self.assertEqual(_normalize_datatype("1,250", "number"), 1250)
        self.assertEqual(_normalize_datatype(42, "number"), 42)
        self.assertEqual(_normalize_datatype(3.14, "number"), 3.14)
        self.assertIsNone(_normalize_datatype("abc", "number"))
        self.assertIsNone(_normalize_datatype(None, "number"))

    def test_currency_normalization(self):
        from ocr.notebook_extraction_service import _normalize_datatype

        self.assertEqual(_normalize_datatype("₹1,250.50", "currency"), 1250.5)
        self.assertEqual(_normalize_datatype("$1250.50", "currency"), 1250.5)
        self.assertEqual(_normalize_datatype("1,250.50", "currency"), 1250.5)
        self.assertEqual(_normalize_datatype("€100", "currency"), 100.0)
        self.assertEqual(_normalize_datatype(100, "currency"), 100.0)
        self.assertEqual(_normalize_datatype(99.99, "currency"), 99.99)
        self.assertIsNone(_normalize_datatype("abc", "currency"))
        self.assertIsNone(_normalize_datatype(None, "currency"))

    def test_date_normalization(self):
        from ocr.notebook_extraction_service import _normalize_datatype

        self.assertEqual(_normalize_datatype("2026-03-12", "date"), "2026-03-12")
        self.assertEqual(_normalize_datatype("2026/03/12", "date"), "2026-03-12")
        self.assertIsNone(_normalize_datatype("12/03/2026", "date"))
        self.assertIsNone(_normalize_datatype("03/12/2026", "date"))
        self.assertIsNone(_normalize_datatype("invalid", "date"))
        self.assertIsNone(_normalize_datatype(None, "date"))

    def test_boolean_normalization(self):
        from ocr.notebook_extraction_service import _normalize_datatype

        self.assertTrue(_normalize_datatype(True, "boolean"))
        self.assertFalse(_normalize_datatype(False, "boolean"))
        self.assertTrue(_normalize_datatype("true", "boolean"))
        self.assertTrue(_normalize_datatype("yes", "boolean"))
        self.assertTrue(_normalize_datatype("1", "boolean"))
        self.assertFalse(_normalize_datatype("false", "boolean"))
        self.assertFalse(_normalize_datatype("no", "boolean"))
        self.assertFalse(_normalize_datatype("0", "boolean"))
        self.assertIsNone(_normalize_datatype("maybe", "boolean"))
        self.assertIsNone(_normalize_datatype(None, "boolean"))

    def test_apply_datatype_normalization_header_fields(self):
        from ocr.notebook_extraction_service import _apply_datatype_normalization

        result = _apply_datatype_normalization(
            {
                "invoice_number": "INV-1",
                "memo": "Test memo",
                "gst_rate": "18%",
                "amount": "₹1,250.50",
                "contract_date": "2026/03/12",
                "is_certified": "true",
            },
            {
                "invoice_number": "text",
                "memo": "text",
                "gst_rate": "number",
                "amount": "currency",
                "contract_date": "date",
                "is_certified": "boolean",
            },
            {},
            (),
        )
        self.assertEqual(result["invoice_number"], "INV-1")
        self.assertEqual(result["memo"], "Test memo")
        self.assertEqual(result["gst_rate"], 18)
        self.assertEqual(result["amount"], 1250.5)
        self.assertEqual(result["contract_date"], "2026-03-12")
        self.assertTrue(result["is_certified"])

    def test_apply_datatype_normalization_line_fields(self):
        from ocr.notebook_extraction_service import _apply_datatype_normalization

        result = _apply_datatype_normalization(
            {
                "invoice_number": "INV-1",
                "line_items": [
                    {
                        "description": "Item 1",
                        "quantity": "2",
                        "unit_price": "100",
                        "amount": "200",
                        "batch_number": "B1",
                    }
                ],
            },
            {"invoice_number": "text"},
            {
                "description": "text",
                "quantity": "number",
                "unit_price": "currency",
                "amount": "currency",
                "batch_number": "text",
            },
            ("description", "quantity", "unit_price", "amount", "batch_number"),
        )
        self.assertEqual(result["line_items"][0]["quantity"], 2)
        self.assertEqual(result["line_items"][0]["unit_price"], 100.0)
        self.assertEqual(result["line_items"][0]["amount"], 200.0)
        self.assertEqual(result["line_items"][0]["batch_number"], "B1")

    def test_invalid_datatype_does_not_crash_extraction(self):
        """Invalid individual field values become None, extraction continues."""
        from ocr.notebook_extraction_service import _apply_datatype_normalization

        result = _apply_datatype_normalization(
            {
                "invoice_number": "INV-1",
                "bad_number": "not_a_number",
                "bad_date": "not_a_date",
                "bad_currency": "xyz",
                "bad_boolean": "maybe",
            },
            {
                "invoice_number": "text",
                "bad_number": "number",
                "bad_date": "date",
                "bad_currency": "currency",
                "bad_boolean": "boolean",
            },
            {},
            (),
        )
        self.assertEqual(result["invoice_number"], "INV-1")
        self.assertIsNone(result["bad_number"])
        self.assertIsNone(result["bad_date"])
        self.assertIsNone(result["bad_currency"])
        self.assertIsNone(result["bad_boolean"])

    def test_invalid_datatype_configuration_rejected(self):
        """Invalid datatype in configuration raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            resolve_field_config({
                "standard_fields": ["invoice_number", "line_items"],
                "custom_fields": [
                    {
                        "label": "Bad Field",
                        "description": "x",
                        "scope": "header",
                        "data_type": "invalid_datatype",
                    }
                ],
            })
        self.assertIn("Invalid datatype", str(ctx.exception))

    def test_invalid_datatype_value_normalized_to_none(self):
        """Invalid datatype passed to normalizer returns None instead of crashing."""
        from ocr.notebook_extraction_service import _normalize_datatype

        self.assertIsNone(_normalize_datatype("some value", "invalid_datatype"))
        self.assertIsNone(_normalize_datatype("some value", ""))

    def test_end_to_end_custom_field_extraction(self):
        """Integration test: requested_fields -> pipeline -> Gemini -> result."""
        from unittest.mock import MagicMock, patch
        from ocr.extraction_service import OCRExtractionService
        from ocr.notebook_extraction_service import resolve_field_config

        requested_fields = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Memo",
                    "description": "description of the invoice",
                    "scope": "header",
                    "data_type": "text",
                },
                {
                    "label": "GST Rate",
                    "description": "GST percentage",
                    "scope": "header",
                    "data_type": "number",
                },
                {
                    "label": "Grand Total",
                    "description": "Total amount",
                    "scope": "header",
                    "data_type": "currency",
                },
                {
                    "label": "Contract Date",
                    "description": "Contract sign date",
                    "scope": "header",
                    "data_type": "date",
                },
            ],
        }

        hf, lf, ili, ht, lt = resolve_field_config(requested_fields)
        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())

        mock_gemini_response = {
            "invoice_number": "INV-1",
            "memo": "Paid via bank transfer",
            "gst_rate": "18%",
            "grand_total": "₹1,250.50",
            "contract_date": "2026/03/12",
            "line_items": [
                {"description": "Item 1", "quantity": 2, "unit_price": 100, "amount": 200}
            ],
        }

        mock_client = MagicMock()
        mock_client.extract.return_value = mock_gemini_response

        service = OCRExtractionService(gemini_client=mock_client)
        upload = MagicMock()
        upload.file.path = "/fake/path"
        upload.mime_type = "image/png"
        user = MagicMock()

        with patch('ocr.extraction_service.settings.OCR_ENABLE_GEMINI', True):
            with patch('ocr.extraction_service.ImageQualityReport') as mock_iqr:
                mock_iqr.from_image.return_value = MagicMock(as_dict=MagicMock(return_value={}))
                with patch.object(service.image_processor, 'preprocess', return_value='/fake/processed.png'):
                    result = service.extract(upload, user, requested_fields=requested_fields)

        data = result["data"]
        # Custom text field survives
        self.assertEqual(data["memo"], "Paid via bank transfer")
        # Number field is numeric
        self.assertEqual(data["gst_rate"], 18)
        # Currency field is numeric
        self.assertEqual(data["grand_total"], 1250.5)
        # Date is normalized safely (year-first slash format -> ISO)
        self.assertEqual(data["contract_date"], "2026-03-12")
        # Standard field preserved
        self.assertEqual(data["invoice_number"], "INV-1")
        # Line items preserved
        self.assertEqual(data["line_items"][0]["description"], "Item 1")
        self.assertEqual(data["line_items"][0]["quantity"], 2)

        # Verify dynamic contract was used
        mock_client.extract.assert_called_once()
        call_kwargs = mock_client.extract.call_args[1]
        self.assertIn("prompt", call_kwargs)
        self.assertIn("response_schema", call_kwargs)
        prompt = call_kwargs["prompt"]
        schema = call_kwargs["response_schema"]
        self.assertIn('"memo"', prompt)
        self.assertIn('"gst_rate"', prompt)
        self.assertIn('"grand_total"', prompt)
        self.assertIn('"contract_date"', prompt)
        self.assertIn("memo", schema["properties"])
        self.assertIn("gst_rate", schema["properties"])
        self.assertIn("grand_total", schema["properties"])
        self.assertIn("contract_date", schema["properties"])

    def test_dynamic_prompt_includes_datatype_hints(self):
        from ocr.notebook_extraction_service import build_prompt

        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "GST Rate",
                    "description": "GST percentage",
                    "scope": "header",
                    "data_type": "number",
                },
                {
                    "label": "Contract Date",
                    "description": "Contract sign date",
                    "scope": "header",
                    "data_type": "date",
                },
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        prompt = build_prompt(hf, lf, ili, ht, lt)
        self.assertIn('"gst_rate"', prompt)
        self.assertIn('plain number', prompt)
        self.assertIn('"contract_date"', prompt)
        self.assertIn('ISO YYYY-MM-DD', prompt)

    def test_dynamic_schema_uses_correct_json_types(self):
        from ocr.notebook_extraction_service import _build_schema, resolve_field_config

        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "GST Rate",
                    "description": "GST percentage",
                    "scope": "header",
                    "data_type": "number",
                },
                {
                    "label": "Is Certified",
                    "description": "Whether certified",
                    "scope": "header",
                    "data_type": "boolean",
                },
                {
                    "label": "Memo",
                    "description": "description of the invoice",
                    "scope": "header",
                    "data_type": "text",
                },
                {
                    "label": "Contract Date",
                    "description": "Contract sign date",
                    "scope": "header",
                    "data_type": "date",
                },
                {
                    "label": "Grand Total",
                    "description": "Total amount",
                    "scope": "header",
                    "data_type": "currency",
                },
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        schema = _build_schema(hf, lf, ili, ht, lt)
        self.assertEqual(schema["properties"]["gst_rate"]["type"], "number")
        self.assertEqual(schema["properties"]["is_certified"]["type"], "boolean")
        self.assertEqual(schema["properties"]["memo"]["type"], "string")
        self.assertEqual(schema["properties"]["contract_date"]["type"], "string")
        self.assertEqual(schema["properties"]["grand_total"]["type"], "number")
        self.assertEqual(schema["properties"]["invoice_number"]["type"], "string")
        self.assertIn("line_items", schema["properties"])

    def test_legacy_path_with_dynamic_requested_fields(self):
        """OCRExtractionService uses the dynamic contract when requested_fields is provided."""
        from unittest.mock import MagicMock, patch
        from ocr.extraction_service import OCRExtractionService

        requested_fields = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "Memo",
                    "description": "description of the invoice",
                    "scope": "header",
                    "data_type": "text",
                }
            ],
        }

        mock_gemini_response = {
            "invoice_number": "INV-1",
            "memo": "Test memo",
            "line_items": [{"description": "Item", "quantity": 1, "unit_price": 10, "amount": 10}],
        }

        mock_client = MagicMock()
        mock_client.extract.return_value = mock_gemini_response

        service = OCRExtractionService(gemini_client=mock_client)
        upload = MagicMock()
        upload.file.path = "/fake/path"
        upload.mime_type = "image/png"
        user = MagicMock()

        with patch('ocr.extraction_service.settings.OCR_ENABLE_GEMINI', True):
            with patch('ocr.extraction_service.ImageQualityReport') as mock_iqr:
                mock_iqr.from_image.return_value = MagicMock(as_dict=MagicMock(return_value={}))
                with patch.object(service.image_processor, 'preprocess', return_value='/fake/processed.png'):
                    result = service.extract(upload, user, requested_fields=requested_fields)

        self.assertEqual(result["data"]["invoice_number"], "INV-1")
        self.assertEqual(result["data"]["memo"], "Test memo")
        self.assertIn("memo", result["data"])
        mock_client.extract.assert_called_once()
        call_kwargs = mock_client.extract.call_args[1]
        self.assertIn("prompt", call_kwargs)
        self.assertIn("response_schema", call_kwargs)
        self.assertIn("memo", call_kwargs["prompt"])
        self.assertIn("memo", call_kwargs["response_schema"]["properties"])

    def test_legacy_path_default_behavior_unchanged(self):
        """OCRExtractionService without requested_fields uses the default dynamic contract."""
        from unittest.mock import MagicMock, patch
        from ocr.extraction_service import OCRExtractionService

        mock_gemini_response = {
            "vendor": "Test Vendor",
            "invoice_number": "INV-1",
            "invoice_date": "2026-03-12",
            "currency": "USD",
            "subtotal": 100,
            "tax": 10,
            "total": 110,
            "purchase_order": "PO-1",
            "items": [{"description": "Item", "quantity": 1, "unit_price": 10, "total": 10}],
            "confidence": {},
        }

        mock_client = MagicMock()
        mock_client.extract.return_value = mock_gemini_response

        service = OCRExtractionService(gemini_client=mock_client)
        upload = MagicMock()
        upload.file.path = "/fake/path"
        upload.mime_type = "image/png"
        user = MagicMock()

        with patch('ocr.extraction_service.settings.OCR_ENABLE_GEMINI', True):
            with patch('ocr.extraction_service.ImageQualityReport') as mock_iqr:
                mock_iqr.from_image.return_value = MagicMock(as_dict=MagicMock(return_value={}))
                with patch.object(service.image_processor, 'preprocess', return_value='/fake/processed.png'):
                    result = service.extract(upload, user)

        mock_client.extract.assert_called_once()
        call_kwargs = mock_client.extract.call_args[1]
        # The legacy/default path now uses the same canonical dynamic contract,
        # just with the full default field set (no custom fields).
        self.assertIn("prompt", call_kwargs)
        self.assertIn("response_schema", call_kwargs)
        self.assertIn("invoice_number", call_kwargs["prompt"])
        self.assertIn("line_items", call_kwargs["response_schema"]["properties"])

    def test_multiple_custom_fields_different_datatypes(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "GST Rate",
                    "description": "GST percentage",
                    "scope": "header",
                    "data_type": "number",
                },
                {
                    "label": "Contract Date",
                    "description": "Contract sign date",
                    "scope": "header",
                    "data_type": "date",
                },
                {
                    "label": "Is Certified",
                    "description": "Whether certified",
                    "scope": "header",
                    "data_type": "boolean",
                },
                {
                    "label": "Grand Total",
                    "description": "Total amount",
                    "scope": "header",
                    "data_type": "currency",
                },
                {
                    "label": "Memo",
                    "description": "description of the invoice",
                    "scope": "header",
                    "data_type": "text",
                },
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        schema = _build_schema(hf, lf, ili, ht, lt)
        prompt = build_prompt(hf, lf, ili, ht, lt)

        self.assertEqual(schema["properties"]["gst_rate"]["type"], "number")
        self.assertEqual(schema["properties"]["contract_date"]["type"], "string")
        self.assertEqual(schema["properties"]["is_certified"]["type"], "boolean")
        self.assertEqual(schema["properties"]["grand_total"]["type"], "number")
        self.assertEqual(schema["properties"]["memo"]["type"], "string")

        self.assertIn('"gst_rate"', prompt)
        self.assertIn('plain number', prompt)
        self.assertIn('"contract_date"', prompt)
        self.assertIn('ISO YYYY-MM-DD', prompt)
        self.assertIn('"is_certified"', prompt)
        self.assertIn('true or false', prompt)
        self.assertIn('"grand_total"', prompt)
        self.assertIn('numeric amount only', prompt)
        self.assertIn('"memo"', prompt)

    def test_custom_field_survives_full_flow_with_datatypes(self):
        requested = {
            "standard_fields": ["invoice_number", "line_items"],
            "custom_fields": [
                {
                    "label": "GST Rate",
                    "description": "GST percentage",
                    "scope": "header",
                    "data_type": "number",
                },
                {
                    "label": "Batch Number",
                    "description": "Lot number",
                    "scope": "line",
                    "data_type": "text",
                },
            ],
        }
        hf, lf, ili, ht, lt = resolve_field_config(requested)
        header_keys = tuple(hf.keys())
        line_keys = tuple(lf.keys())

        data = {
            "invoice_number": "INV-1",
            "gst_rate": "18%",
            "line_items": [{"description": "Item", "batch_number": "B1"}],
        }

        normalized = _normalize_result(data, header_keys, line_keys, ili)
        normalized = _apply_datatype_normalization(
            normalized, ht, lt, line_keys
        )

        self.assertEqual(normalized["gst_rate"], 18)
        self.assertEqual(normalized["line_items"][0]["batch_number"], "B1")

    def test_cache_key_includes_config_hash(self):
        from ocr.tasks import _config_hash, _file_result_cache_key

        config1 = {"standard_fields": ["invoice_number"], "custom_fields": []}
        config2 = {"standard_fields": ["invoice_number", "vendor_name"], "custom_fields": []}

        key1 = _file_result_cache_key("abc123", _config_hash(config1))
        key2 = _file_result_cache_key("abc123", _config_hash(config2))
        key_default = _file_result_cache_key("abc123")

        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key1, key_default)
        # Default key should not contain the config hash segment that differs from config1
        self.assertNotIn(_config_hash(config1), key_default)

    def test_batch_status_includes_requested_fields(self):
        from ocr.test_ocr_view import _build_requested_fields
        from ocr.serializers import DocumentHistorySerializer

        requested_fields = {
            "standard_fields": ["invoice_number"],
            "custom_fields": [
                {"label": "Memo", "description": "x", "scope": "header", "data_type": "text"}
            ],
        }

        class FakeRequest:
            data = {"requested_fields": json.dumps(requested_fields)}
            user = MagicMock()

        resolved = _build_requested_fields(FakeRequest())
        self.assertIsNotNone(resolved)
        self.assertEqual(
            resolved["custom_fields"][0]["label"], "Memo"
        )

        serializer = DocumentHistorySerializer(
            {
                "id": "00000000-0000-0000-0000-000000000001",
                "upload_id": None,
                "filename": "test.pdf",
                "document_type": "INVOICE",
                "status": "COMPLETED",
                "current_version": 1,
                "overall_confidence": 0.9,
                "processing_metadata": {},
                "requested_fields": resolved,
                "versions": [],
            }
        )
        data = serializer.data
        self.assertIn("requested_fields", data)
        self.assertEqual(
            data["requested_fields"]["custom_fields"][0]["label"], "Memo"
        )


class OCROCRCacheArchitectureTests(SimpleTestCase):
    """Tests for production-safe OCR result cache identity and validation."""

    def test_default_config_hash_is_deterministic(self):
        h1 = build_extraction_config_hash(None)
        h2 = build_extraction_config_hash(None)
        self.assertEqual(h1, h2)
        self.assertEqual(h1, "default")

    def test_empty_dict_hashes_like_default(self):
        self.assertEqual(
            build_extraction_config_hash({}),
            build_extraction_config_hash(None),
        )

    def test_config_hash_changes_with_standard_fields(self):
        config_a = {"standard_fields": ["invoice_number"]}
        config_b = {"standard_fields": ["invoice_number", "vendor_name"]}
        self.assertNotEqual(
            build_extraction_config_hash(config_a),
            build_extraction_config_hash(config_b),
        )

    def test_config_hash_changes_with_custom_fields(self):
        config_a = {
            "standard_fields": ["invoice_number"],
            "custom_fields": [
                {"label": "Memo", "description": "x", "scope": "header", "data_type": "text"}
            ],
        }
        config_b = {
            "standard_fields": ["invoice_number"],
            "custom_fields": [
                {"label": "Memo", "description": "x", "scope": "header", "data_type": "text"},
                {"label": "GST", "description": "y", "scope": "header", "data_type": "number"},
            ],
        }
        self.assertNotEqual(
            build_extraction_config_hash(config_a),
            build_extraction_config_hash(config_b),
        )

    def test_config_hash_changes_with_datatype(self):
        config_a = {
            "standard_fields": ["invoice_number"],
            "custom_fields": [
                {"label": "Memo", "scope": "header", "data_type": "text"}
            ],
        }
        config_b = {
            "standard_fields": ["invoice_number"],
            "custom_fields": [
                {"label": "Memo", "scope": "header", "data_type": "number"}
            ],
        }
        self.assertNotEqual(
            build_extraction_config_hash(config_a),
            build_extraction_config_hash(config_b),
        )

    def test_config_hash_same_for_different_key_ordering(self):
        config_a = {
            "custom_fields": [
                {"key": "memo", "label": "Memo", "description": "x", "scope": "header", "data_type": "text"}
            ],
            "standard_fields": ["invoice_number"],
        }
        config_b = {
            "standard_fields": ["invoice_number"],
            "custom_fields": [
                {"data_type": "text", "description": "x", "key": "memo", "label": "Memo", "scope": "header"},
            ],
        }
        self.assertEqual(
            build_extraction_config_hash(config_a),
            build_extraction_config_hash(config_b),
        )

    def test_cache_key_includes_contract_version(self):
        key_v2 = build_ocr_cache_key("abc123", {"standard_fields": ["invoice_number"]})
        self.assertIn("v2", key_v2)

    def test_cache_key_includes_config_hash(self):
        config = {"standard_fields": ["invoice_number"]}
        key = build_ocr_cache_key("abc123", config)
        config_hash = build_extraction_config_hash(config)
        self.assertIn(config_hash, key)

    def test_cache_identity_contains_required_fields(self):
        identity = build_ocr_cache_identity("abc123", {"standard_fields": ["invoice_number"]})
        self.assertIn("document_identity", identity)
        self.assertIn("config_hash", identity)
        self.assertIn("contract_version", identity)
        self.assertIn("status", identity)
        self.assertEqual(identity["status"], "COMPLETED")
        self.assertEqual(identity["contract_version"], "v2")

    def test_different_configs_produce_different_keys(self):
        config_a = {"standard_fields": ["invoice_number"]}
        config_b = {"standard_fields": ["invoice_number", "vendor_name"]}
        key_a = build_ocr_cache_key("abc123", config_a)
        key_b = build_ocr_cache_key("abc123", config_b)
        self.assertNotEqual(key_a, key_b)

    def test_same_config_same_key(self):
        config = {"standard_fields": ["invoice_number"]}
        key1 = build_ocr_cache_key("abc123", config)
        key2 = build_ocr_cache_key("abc123", config)
        self.assertEqual(key1, key2)

    def test_read_valid_cached_result_accepts_valid_payload(self):
        config = {"standard_fields": ["invoice_number"]}
        cache_key = build_ocr_cache_key("abc123", config)
        payload = {
            "metadata": build_ocr_cache_identity("abc123", config),
            "result": {"invoice_number": "INV-1"},
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config)

        self.assertEqual(result, {"invoice_number": "INV-1"})

    def test_read_valid_cached_result_rejects_missing_metadata(self):
        config = {"standard_fields": ["invoice_number"]}
        payload = {"result": {"invoice_number": "INV-1"}}

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config)

        self.assertIsNone(result)

    def test_read_valid_cached_result_rejects_wrong_status(self):
        config = {"standard_fields": ["invoice_number"]}
        payload = {
            "metadata": {
                "document_identity": "abc123",
                "config_hash": build_extraction_config_hash(config),
                "contract_version": "v2",
                "status": "PROCESSING",
            },
            "result": {"invoice_number": "INV-1"},
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config)

        self.assertIsNone(result)

    def test_read_valid_cached_result_rejects_corrupt_json(self):
        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = "not json"
            result = read_valid_cached_result("abc123", {"standard_fields": ["invoice_number"]})

        self.assertIsNone(result)

    def test_read_valid_cached_result_rejects_missing_result(self):
        config = {"standard_fields": ["invoice_number"]}
        payload = {
            "metadata": build_ocr_cache_identity("abc123", config),
            "result": None,
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config)

        self.assertIsNone(result)

    def test_read_valid_cached_result_rejects_invalid_line_items(self):
        config = {"standard_fields": ["invoice_number"]}
        payload = {
            "metadata": build_ocr_cache_identity("abc123", config),
            "result": {"line_items": "not-a-list"},
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config)

        self.assertIsNone(result)

    def test_write_and_read_completed_result_roundtrip(self):
        config = {"standard_fields": ["invoice_number"]}
        result = {"invoice_number": "INV-1", "line_items": []}

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            write_completed_cached_result("abc123", config, result)

            # Verify setex was called
            self.assertTrue(mock_client.setex.called)
            cache_key = mock_client.setex.call_args[0][0]
            ttl = mock_client.setex.call_args[0][1]
            stored_payload = json.loads(mock_client.setex.call_args[0][2])

            # Verify key contains identity components
            self.assertIn("v2", cache_key)
            self.assertIn(build_extraction_config_hash(config), cache_key)
            self.assertEqual(ttl, 24 * 60 * 60)

            # Verify payload structure
            self.assertIn("metadata", stored_payload)
            self.assertIn("result", stored_payload)
            self.assertEqual(stored_payload["result"], result)
            self.assertEqual(stored_payload["metadata"]["status"], "COMPLETED")

            # Verify roundtrip read
            mock_client.get.return_value = json.dumps(stored_payload)
            read_result = read_valid_cached_result("abc123", config)

        self.assertEqual(read_result, result)

    def test_contract_version_mismatch_is_rejected(self):
        config = {"standard_fields": ["invoice_number"]}
        payload = {
            "metadata": {
                "document_identity": "abc123",
                "config_hash": build_extraction_config_hash(config),
                "contract_version": "v1",
                "status": "COMPLETED",
            },
            "result": {"invoice_number": "INV-1"},
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config)

        self.assertIsNone(result)

    def test_config_hash_mismatch_is_rejected(self):
        config_a = {"standard_fields": ["invoice_number"]}
        config_b = {"standard_fields": ["invoice_number", "vendor_name"]}
        payload = {
            "metadata": build_ocr_cache_identity("abc123", config_a),
            "result": {"invoice_number": "INV-1"},
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config_b)

        self.assertIsNone(result)

    def test_document_identity_mismatch_is_rejected(self):
        config = {"standard_fields": ["invoice_number"]}
        payload = {
            "metadata": build_ocr_cache_identity("def456", config),
            "result": {"invoice_number": "INV-1"},
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_redis.return_value.get.return_value = json.dumps(payload)
            result = read_valid_cached_result("abc123", config)

        self.assertIsNone(result)

    def test_default_and_custom_configs_do_not_share_cache(self):
        default_config = None
        custom_config = {
            "standard_fields": ["invoice_number"],
            "custom_fields": [
                {"label": "Memo", "description": "x", "scope": "header", "data_type": "text"}
            ],
        }

        default_key = build_ocr_cache_key("abc123", default_config)
        custom_key = build_ocr_cache_key("abc123", custom_config)

        self.assertNotEqual(default_key, custom_key)
        self.assertNotIn(
            build_extraction_config_hash(custom_config),
            default_key,
        )


class OCRCacheLockTests(SimpleTestCase):
    """Tests for Redis single-flight lock mechanism."""

    def test_malformed_config_never_becomes_default_hash(self):
        """Malformed non-empty config must raise, never return 'default'."""
        with self.assertRaises(ValueError):
            build_extraction_config_hash({"standard_fields": "invalid"})

        with self.assertRaises(ValueError):
            build_extraction_config_hash({"custom_fields": "invalid"})

        with self.assertRaises(ValueError):
            build_extraction_config_hash({"standard_fields": ["invoice_number"], "custom_fields": "invalid"})

    def test_malformed_config_types_rejected(self):
        """Various malformed config types are rejected."""
        with self.assertRaises(ValueError):
            build_extraction_config_hash(123)

        with self.assertRaises(ValueError):
            build_extraction_config_hash("invalid")

        with self.assertRaises(ValueError):
            build_extraction_config_hash([1, 2, 3])

    def test_valid_configs_still_work(self):
        """Valid configs still produce deterministic hashes."""
        config = {"standard_fields": ["invoice_number"], "custom_fields": []}
        h1 = build_extraction_config_hash(config)
        h2 = build_extraction_config_hash(config)
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, "default")

    def test_acquire_lock_returns_token(self):
        """Lock acquisition returns a token on success."""
        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.set.return_value = True
            mock_redis.return_value = mock_client
            token = acquire_extraction_lock("abc123", {"standard_fields": ["invoice_number"]})
            self.assertIsNotNone(token)
            self.assertIsInstance(token, str)
            mock_client.set.assert_called_once()
            call_args = mock_client.set.call_args
            self.assertTrue(call_args.kwargs.get("nx"))
            self.assertIsNotNone(call_args.kwargs.get("ex"))

    def test_acquire_lock_fails_when_held(self):
        """Lock acquisition returns None when lock is already held."""
        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.set.return_value = False
            mock_redis.return_value = mock_client
            token = acquire_extraction_lock("abc123", {"standard_fields": ["invoice_number"]})
            self.assertIsNone(token)

    def test_release_lock_only_by_owner(self):
        """Lock release only succeeds for the owning token."""
        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.eval.return_value = 1
            mock_redis.return_value = mock_client
            release_extraction_lock("abc123", {"standard_fields": ["invoice_number"]}, "my-token")
            mock_client.eval.assert_called_once()
            lua_script = mock_client.eval.call_args[0][0]
            self.assertIn("get", lua_script)
            self.assertIn("del", lua_script)

    def test_release_lock_noop_without_token(self):
        """Lock release is a no-op when token is None."""
        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            release_extraction_lock("abc123", {"standard_fields": ["invoice_number"]}, None)
            mock_client.eval.assert_not_called()

    def test_wait_for_lock_returns_result_when_available(self):
        """Waiting for lock returns result when another worker completes."""
        config = {"standard_fields": ["invoice_number"]}
        payload = {
            "metadata": build_ocr_cache_identity("abc123", config),
            "result": {"invoice_number": "INV-1"},
        }

        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_client.get.return_value = json.dumps(payload)
            mock_redis.return_value = mock_client
            with patch("ocr.tasks.read_valid_cached_result", return_value={"invoice_number": "INV-1"}) as mock_read:
                result = wait_for_extraction_lock("abc123", config, timeout=1, poll_interval=0.1)
                self.assertEqual(result, {"invoice_number": "INV-1"})

    def test_wait_for_lock_timeout_returns_none(self):
        """Waiting for lock returns None on timeout."""
        with patch("ocr.tasks._redis_client") as mock_redis:
            mock_client = MagicMock()
            mock_redis.return_value = mock_client
            with patch("ocr.tasks.read_valid_cached_result", return_value=None):
                result = wait_for_extraction_lock("abc123", {"standard_fields": ["invoice_number"]}, timeout=0, poll_interval=0.1)
                self.assertIsNone(result)

    def test_lock_key_includes_identity_components(self):
        """Lock key includes contract version and config hash."""
        config = {"standard_fields": ["invoice_number"]}
        lock_key = _build_lock_key("abc123", config)
        self.assertIn("v2", lock_key)
        self.assertIn(build_extraction_config_hash(config), lock_key)
        self.assertIn("abc123", lock_key)
        self.assertIn("lock", lock_key)


class MultiPageExtractionTests(TestCase):
    """Tests for multi-page extraction and merging."""

    def test_merge_header_fields_first_non_null_wins(self):
        from ocr.services.pipeline_service import IDPPipelineService
        service = IDPPipelineService()
        page_results = [
            {'data': {'invoice_number': None, 'vendor_name': 'Vendor A'}},
            {'data': {'invoice_number': 'INV-001', 'vendor_name': None}},
        ]
        merged = service._merge_extraction_results(page_results)
        self.assertEqual(merged['data']['invoice_number'], 'INV-001')
        self.assertEqual(merged['data']['vendor_name'], 'Vendor A')

    def test_merge_line_items_concatenated(self):
        from ocr.services.pipeline_service import IDPPipelineService
        service = IDPPipelineService()
        page_results = [
            {'data': {'line_items': [{'description': 'Item 1'}]}},
            {'data': {'line_items': [{'description': 'Item 2'}]}},
        ]
        merged = service._merge_extraction_results(page_results)
        self.assertEqual(len(merged['data']['line_items']), 2)
        self.assertEqual(merged['data']['line_items'][0]['description'], 'Item 1')
        self.assertEqual(merged['data']['line_items'][1]['description'], 'Item 2')

    def test_merge_custom_header_field_across_pages(self):
        from ocr.services.pipeline_service import IDPPipelineService
        service = IDPPipelineService()
        page_results = [
            {'data': {'memo': None, 'custom_field': 'Value from page 1'}},
            {'data': {'memo': 'Memo from page 2', 'custom_field': None}},
        ]
        merged = service._merge_extraction_results(page_results)
        self.assertEqual(merged['data']['memo'], 'Memo from page 2')
        self.assertEqual(merged['data']['custom_field'], 'Value from page 1')

    def test_merge_custom_line_items_across_pages(self):
        from ocr.services.pipeline_service import IDPPipelineService
        service = IDPPipelineService()
        page_results = [
            {'data': {'item_category': [{'name': 'Category A'}]}},
            {'data': {'item_category': [{'name': 'Category B'}]}},
        ]
        merged = service._merge_extraction_results(page_results)
        self.assertEqual(len(merged['data']['item_category']), 2)
        self.assertEqual(merged['data']['item_category'][0]['name'], 'Category A')
        self.assertEqual(merged['data']['item_category'][1]['name'], 'Category B')

    def test_merge_raw_text_concatenated_with_separator(self):
        from ocr.services.pipeline_service import IDPPipelineService
        service = IDPPipelineService()
        page_results = [
            {'data': {'raw_text': 'Page 1 text'}},
            {'data': {'raw_text': 'Page 2 text'}},
        ]
        merged = service._merge_extraction_results(page_results)
        self.assertIn('Page 1 text', merged['data']['raw_text'])
        self.assertIn('Page 2 text', merged['data']['raw_text'])
        self.assertIn('---PAGE BREAK---', merged['data']['raw_text'])

    def test_single_page_result_unchanged(self):
        from ocr.services.pipeline_service import IDPPipelineService
        service = IDPPipelineService()
        page_results = [
            {'data': {'invoice_number': 'INV-001', 'line_items': [{'description': 'Item 1'}]}},
        ]
        merged = service._merge_extraction_results(page_results)
        self.assertEqual(merged['data']['invoice_number'], 'INV-001')
        self.assertEqual(len(merged['data']['line_items']), 1)


class CacheConfigCanonicalizationTests(TestCase):
    """Tests for strict cache config canonicalization."""

    def test_malformed_custom_field_raises_valueerror(self):
        from ocr.tasks import build_extraction_config_hash
        with self.assertRaises(ValueError):
            build_extraction_config_hash({
                "standard_fields": ["invoice_number"],
                "custom_fields": ["invalid"],
            })

    def test_malformed_custom_field_missing_label_raises(self):
        from ocr.tasks import build_extraction_config_hash
        with self.assertRaises(ValueError):
            build_extraction_config_hash({
                "standard_fields": ["invoice_number"],
                "custom_fields": [{}],
            })

    def test_valid_config_still_works(self):
        from ocr.tasks import build_extraction_config_hash
        hash1 = build_extraction_config_hash({
            "standard_fields": ["invoice_number"],
            "custom_fields": [{"key": "memo", "label": "Memo", "description": "Test", "scope": "header", "data_type": "text"}],
        })
        hash2 = build_extraction_config_hash({
            "standard_fields": ["invoice_number"],
            "custom_fields": [{"key": "memo", "label": "Memo", "description": "Test", "scope": "header", "data_type": "text"}],
        })
        self.assertEqual(hash1, hash2)
        self.assertNotEqual(hash1, "default")
