from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.test import SimpleTestCase

from netsuite.diagnostics_service import _build_validation_information
from netsuite.oauth import netsuite_vendor_bill_url
from netsuite.services import (
    NetSuiteFieldMappingService,
    NetSuiteVendorBillPostingService,
    NetSuiteValidationService,
    _build_template_netsuite_mappings,
)
from netsuite.validation_error_groups import build_validation_error_groups


class ExtractedItemKeywordMatchingTests(SimpleTestCase):
    def setUp(self):
        self.service = NetSuiteValidationService()
        self.service._find_item_candidates_for_tokens_live = Mock(return_value=[
            {
                "id": "1",
                "itemid": "Nike Air Max",
                "displayname": "Nike Air Max",
                "description": "Black Shoes XL",
            },
            {
                "id": "2",
                "itemid": "Adidas Runner",
                "displayname": "Adidas Runner",
                "description": "Black Shoes XL",
            },
            {
                "id": "3",
                "itemid": "Woodland Boots",
                "displayname": "Woodland Boots",
                "description": "Black Boots XL",
            },
        ])

    def test_a_single_complete_row_match_is_selected_automatically(self):
        result = self.service._match_one_extracted_item(
            connection=Mock(),
            extracted_name="Black Boots XL",
            cached_items=[],
        )

        self.assertTrue(result["matched"])
        self.assertFalse(result["needs_selection"])
        self.assertEqual(result["match_type"], "unique_all_keywords")
        self.assertEqual(result["selected_item_name"], "Woodland Boots")

    def test_exact_item_name_is_selected_before_other_complete_keyword_matches(self):
        self.service._find_item_candidates_for_tokens_live.return_value = [
            {
                "id": "1",
                "itemid": "Consulting Service",
                "displayname": "Consulting Service",
            },
            {
                "id": "2",
                "itemid": "Consulting Services",
                "displayname": "Consulting Services",
            },
            {
                "id": "3",
                "itemid": "Professional Consulting Service_PK",
                "displayname": "Professional Consulting Service_PK",
            },
        ]

        result = self.service._match_one_extracted_item(
            connection=Mock(),
            extracted_name="Consulting Service",
            cached_items=[],
        )

        self.assertTrue(result["matched"])
        self.assertFalse(result["needs_selection"])
        self.assertEqual(result["match_type"], "exact_name")
        self.assertEqual(result["selected_item_name"], "Consulting Service")

    def test_multiple_complete_row_matches_require_a_dropdown_choice(self):
        self.service._find_item_candidates_for_tokens_live.return_value.append({
            "id": "4",
            "itemid": "Timberland Boots",
            "displayname": "Timberland Boots",
            "description": "Black Boots XL",
        })

        result = self.service._match_one_extracted_item(
            connection=Mock(),
            extracted_name="Black Boots XL",
            cached_items=[],
        )

        self.assertFalse(result["matched"])
        self.assertTrue(result["needs_selection"])
        self.assertEqual(result["match_type"], "multiple_all_keywords")
        self.assertEqual(
            [candidate["name"] for candidate in result["candidates"]],
            ["Timberland Boots", "Woodland Boots"],
        )

    def test_partial_suggestions_require_at_least_two_keywords(self):
        self.service._find_item_candidates_for_tokens_live.return_value = [
            {
                "id": "1",
                "itemid": "Nike Air Max",
                "displayname": "Nike Air Max",
                "description": "Black Shoes XL",
            },
            {
                "id": "5",
                "itemid": "Puma Sports",
                "displayname": "Puma Sports",
                "description": "Red Shoes XL",
            },
        ]

        result = self.service._match_one_extracted_item(
            connection=Mock(),
            extracted_name="Black Boots XL",
            cached_items=[],
        )

        self.assertTrue(result["needs_selection"])
        self.assertEqual(result["match_type"], "partial_keywords")
        self.assertEqual([candidate["name"] for candidate in result["candidates"]], ["Nike Air Max"])

    def test_falls_back_to_all_one_keyword_matches_when_no_higher_score_exists(self):
        self.service._find_item_candidates_for_tokens_live.return_value = [
            {
                "id": "5",
                "itemid": "Puma Sports",
                "displayname": "Puma Sports",
                "description": "Red Shoes XL",
            },
            {
                "id": "6",
                "itemid": "Campus Shoes",
                "displayname": "Campus Shoes",
                "description": "Black Shoes XL",
            },
        ]

        result = self.service._match_one_extracted_item(
            connection=Mock(),
            extracted_name="Black Boots Red",
            cached_items=[],
        )

        self.assertTrue(result["needs_selection"])
        self.assertEqual(result["match_type"], "partial_keywords")
        self.assertEqual([candidate["name"] for candidate in result["candidates"]], ["Campus Shoes", "Puma Sports"])
        self.assertTrue(all(candidate["match_count"] == 1 for candidate in result["candidates"]))


class ValidationErrorGroupingTests(SimpleTestCase):
    def test_groups_identical_line_errors_without_merging_source_rows(self):
        line_items = [
            {
                "item": "6180 Professional Fees",
                "quantity": 1,
                "unit_price": 100,
                "tax_amount": 18,
            },
            {
                "item": "6180 Professional Fees",
                "quantity": 1,
                "unit_price": 100,
                "tax_amount": 18,
            },
            {
                "item": "6180 Professional Fees",
                "quantity": 1,
                "unit_price": 125,
                "tax_amount": 22.5,
            },
        ]
        errors = [
            {
                "type": "ITEM_NOT_FOUND",
                "message": "Item does not exist.",
                "extracted_name": "6180 Professional Fees",
                "line_index": 1,
            },
            {
                "type": "ITEM_NOT_FOUND",
                "message": "Item does not exist.",
                "extracted_name": "6180 Professional Fees",
                "line_index": 2,
            },
            {
                "type": "ITEM_NOT_FOUND",
                "message": "Item does not exist.",
                "extracted_name": "6180 Professional Fees",
                "line_index": 3,
            },
        ]

        groups = build_validation_error_groups(errors, line_items)

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["affected_lines"], [1, 2])
        self.assertEqual(groups[0]["affected_count"], 2)
        self.assertEqual(groups[0]["error_indexes"], [0, 1])
        self.assertEqual(groups[1]["affected_lines"], [3])
        self.assertEqual(len(line_items), 3)

    def test_keeps_header_errors_separate_from_line_error_groups(self):
        errors = [
            {"type": "LOCATION_NOT_FOUND", "message": "Location missing."},
            {"type": "ITEM_NOT_FOUND", "message": "Item missing.", "line_index": 1},
        ]

        groups = build_validation_error_groups(errors, [{"item": "Missing"}])

        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[0]["affected_count"], 0)
        self.assertEqual(groups[1]["affected_lines"], [1])

    def test_ai_diagnostics_receive_one_reference_per_error_group(self):
        validation = SimpleNamespace(
            id="validation-1",
            document_id="document-1",
            version=SimpleNamespace(
                reviewed_json={
                    "line_items": [
                        {"item": "Service", "unit_price": 100},
                        {"item": "Service", "unit_price": 100},
                    ]
                },
                normalized_json={},
            ),
            errors=[
                {
                    "type": "ITEM_NOT_FOUND",
                    "message": "Item does not exist.",
                    "extracted_name": "Service",
                    "line_index": 1,
                },
                {
                    "type": "ITEM_NOT_FOUND",
                    "message": "Item does not exist.",
                    "extracted_name": "Service",
                    "line_index": 2,
                },
            ],
            items=[],
            vendor_extracted_name="Vendor",
            vendor_matched=True,
            vendor_netsuite_id="12",
        )

        references, information = _build_validation_information([validation])

        self.assertEqual(references, ["validation-1:group:0"])
        self.assertEqual(len(information["validations"][0]["errors"]), 1)
        diagnostic_error = information["validations"][0]["errors"][0]["error"]
        self.assertEqual(diagnostic_error["affected_count"], 2)
        self.assertEqual(diagnostic_error["affected_lines"], [1, 2])


class TemplateDrivenVendorBillPayloadTests(SimpleTestCase):
    def test_snapshot_keeps_custom_header_and_item_mappings(self):
        requested_fields = {
            "standard_fields": ["vendor_name", "item"],
            "standard_field_overrides": {
                "vendor_name": {
                    "label": "Supplier",
                    "scope": "header",
                    "data_type": "text",
                    "netsuite_field_id": "entity",
                    "netsuite_field_scope": "body",
                },
                "item": {
                    "label": "Service",
                    "scope": "line",
                    "data_type": "text",
                    "netsuite_field_id": "item",
                    "netsuite_field_scope": "column",
                    "netsuite_field_sublist_id": "item",
                },
            },
            "custom_fields": [
                {
                    "key": "work_order",
                    "label": "Work order",
                    "scope": "header",
                    "data_type": "text",
                    "netsuite_field_id": "custbody_work_order",
                    "netsuite_field_scope": "body",
                },
                {
                    "key": "service_code",
                    "label": "Service code",
                    "scope": "line",
                    "data_type": "text",
                    "netsuite_field_id": "custcol_service_code",
                    "netsuite_field_scope": "column",
                    "netsuite_field_sublist_id": "item",
                },
            ],
        }

        mappings = _build_template_netsuite_mappings(requested_fields)
        by_source = {mapping["source_field_key"]: mapping for mapping in mappings}

        self.assertEqual(by_source["work_order"]["target_field_id"], "custbody_work_order")
        self.assertEqual(by_source["service_code"]["target_field_id"], "custcol_service_code")
        self.assertEqual(by_source["service_code"]["target_sublist_id"], "item")

    def test_numeric_normalisation_uses_saved_mapping_metadata(self):
        value = NetSuiteVendorBillPostingService._normalise_mapped_value(
            "1,250.50",
            {"target_field_id": "custcol_charge", "target_datatype": "currency"},
            line_number=1,
        )

        self.assertEqual(value, 1250.5)


class NetSuiteRecordUrlTests(SimpleTestCase):
    def test_vendor_bill_url_uses_account_domain_and_internal_id(self):
        url = netsuite_vendor_bill_url(
            account_id="1234567_SB1",
            record_id="23662",
        )

        self.assertEqual(
            url,
            "https://1234567-sb1.app.netsuite.com/"
            "app/accounting/transactions/vendbill.nl?id=23662&whence=",
        )


class NetSuiteFieldCatalogueTests(SimpleTestCase):
    def test_includes_feature_specific_sublist_fields(self):
        raw_metadata = {
            "properties": {
                "landedCosts": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "category": {"type": "string"},
                                    "amount": {"type": "number"},
                                },
                            },
                        },
                    },
                },
                "custbody_reference_transaction": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string"},
                        "refName": {"type": "string"},
                    },
                },
                "customLineList": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "customLineValue": {"type": "string"},
                        },
                    },
                },
            },
        }

        catalogue = NetSuiteFieldMappingService._normalise_metadata(
            raw_metadata,
            "vendorBill",
        )

        self.assertEqual(
            [field["field_id"] for field in catalogue["line_fields"]],
            ["category", "amount", "customLineValue"],
        )
        self.assertEqual(
            [field["sublist_id"] for field in catalogue["line_fields"]],
            ["landedcosts", "landedcosts", "customlinelist"],
        )
        self.assertEqual(
            [field["field_id"] for field in catalogue["body_fields"]],
            ["custbody_reference_transaction"],
        )

    def test_keeps_reference_object_custom_column_field(self):
        raw_metadata = {
            "properties": {
                "item": {
                    "type": "object",
                    "properties": {
                        "items": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "custcol_agtax_gst_sac_code": {
                                        "title": "GST SAC Code",
                                        "type": "object",
                                        "properties": {
                                            "id": {"type": "string"},
                                            "refName": {"type": "string"},
                                            "externalId": {"type": "string"},
                                            "links": {"type": "array"},
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        }

        catalogue = NetSuiteFieldMappingService._normalise_metadata(
            raw_metadata,
            "vendorBill",
        )

        self.assertEqual(
            catalogue["line_fields"],
            [
                {
                    "field_id": "custcol_agtax_gst_sac_code",
                    "label": "GST SAC Code",
                    "datatype": "select",
                    "scope": "column",
                    "is_required": False,
                    "is_custom": True,
                    "reference_type": None,
                    "sublist_id": "item",
                },
            ],
        )


class VendorReferenceEnrichmentTests(SimpleTestCase):
    def test_subsidiary_currency_overrides_ai_and_template_values(self):
        service = NetSuiteValidationService()
        connection = SimpleNamespace(status="connected", is_active=True)
        mappings = [
            {"source_scope": "header", "target_field_id": "subsidiary", "source_field_key": "company_unit"},
            {"source_scope": "header", "target_field_id": "currency", "source_field_key": "bill_currency"},
        ]
        service.enrich_missing_vendor_references = Mock(return_value={"changed": {}, "reason": None})
        service._resolve_select_field_live = Mock(return_value="3")
        service._execute_live_suiteql = Mock(return_value={"items": [{"id": "7", "symbol": "INR", "name": "Indian Rupee"}]})
        data = {"company_unit": "India", "bill_currency": "USD"}
        with patch("netsuite.services._build_template_netsuite_mappings", return_value=mappings):
            result = service.enrich_transaction_references(
                data=data, requested_fields={}, user=None, connection=connection,
            )
        self.assertEqual(data["bill_currency"], "INR")
        self.assertEqual(result["changed"]["currency"]["netsuite_id"], "7")

    def test_vendor_enrichment_runs_before_currency_and_failure_clears_ai_currency(self):
        service = NetSuiteValidationService()
        connection = SimpleNamespace(status="connected", is_active=True)
        def enrich(**kwargs):
            kwargs["data"]["subsidiary"] = {"id": "3"}
            return {"changed": {"subsidiary": {"value": "India"}}, "reason": "enriched"}
        service.enrich_missing_vendor_references = Mock(side_effect=enrich)
        service._execute_live_suiteql = Mock(return_value={"items": []})
        mappings = [
            {"source_scope": "header", "target_field_id": key, "source_field_key": key}
            for key in ("subsidiary", "currency")
        ]
        data = {"currency": "USD"}
        with patch("netsuite.services._build_template_netsuite_mappings", return_value=mappings):
            result = service.enrich_transaction_references(
                data=data, requested_fields={}, user=None, connection=connection,
            )
        self.assertIsNone(data["currency"])
        self.assertEqual(result["reason"], "subsidiary_currency_lookup_error")

    def test_currency_lookup_rejects_missing_subsidiary(self):
        service = NetSuiteValidationService()
        with self.assertRaises(ValueError):
            service._fetch_subsidiary_currency_live(connection=None, subsidiary_id=None)

    def test_accepts_a_single_vendor_reference(self):
        reference = NetSuiteValidationService._reference_candidate(
            {"id": "15", "refName": "Pune"}
        )

        self.assertEqual(reference, {"id": "15", "name": "Pune"})

    def test_uses_explicit_primary_reference_from_a_list(self):
        reference = NetSuiteValidationService._reference_candidate(
            [
                {"id": "1", "refName": "India"},
                {"id": "2", "refName": "US", "primary": True},
            ]
        )

        self.assertEqual(reference, {"id": "2", "name": "US"})

    def test_rejects_ambiguous_multi_value_reference(self):
        reference = NetSuiteValidationService._reference_candidate(
            [
                {"id": "15", "refName": "Pune"},
                {"id": "16", "refName": "Bangalore"},
            ]
        )

        self.assertIsNone(reference)
