from django.test import SimpleTestCase

from netsuite.services import (
    NetSuiteVendorBillPostingService,
    _build_template_netsuite_mappings,
)


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
