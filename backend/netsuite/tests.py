from types import SimpleNamespace

from django.test import SimpleTestCase

from netsuite.diagnostics_service import _build_validation_information
from netsuite.oauth import netsuite_vendor_bill_url
from netsuite.services import (
    NetSuiteFieldMappingService,
    NetSuiteVendorBillPostingService,
    _build_template_netsuite_mappings,
)
from netsuite.validation_error_groups import build_validation_error_groups


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
