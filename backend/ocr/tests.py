from django.test import SimpleTestCase
from contextlib import nullcontext
from datetime import datetime
from unittest.mock import Mock, patch

from ocr.notebook_extraction_service import (
    FIELD_DESCRIPTIONS,
    LINE_ITEM_FIELDS,
    FIELD_DATA_TYPES,
    LINE_ITEM_DATA_TYPES,
    get_standard_field_catalog,
    build_prompt,
    resolve_field_config,
    _apply_template_default_values,
)


class OCRExtractionDefaultsTests(SimpleTestCase):
    @patch('ocr.services.extraction_persistence.GeneratedInvoiceNumber.objects.create')
    def test_missing_invoice_number_receives_sequential_default(self, create):
        from ocr.services.extraction_persistence import _apply_initial_defaults
        create.side_effect = [Mock(pk=1), Mock(pk=2)]
        first = {'invoice_number': None, 'location': None}
        second = {'invoice_number': '', 'location': ''}
        _apply_initial_defaults(first)
        _apply_initial_defaults(second)
        self.assertEqual(first, {'invoice_number': 'vendor_bill_inv_1', 'location': None})
        self.assertEqual(second, {'invoice_number': 'vendor_bill_inv_2', 'location': ''})

    @patch('ocr.services.extraction_persistence.GeneratedInvoiceNumber.objects.create')
    def test_existing_ai_or_reviewed_values_are_preserved(self, create):
        from ocr.services.extraction_persistence import _apply_initial_defaults
        original = {'invoice_number': 'INV-1', 'location': 'Delhi'}
        _apply_initial_defaults(original)
        self.assertEqual(original, {'invoice_number': 'INV-1', 'location': 'Delhi'})
        reviewed = {'invoice_number': 'MANUAL-1', 'location': 'Mumbai'}
        _apply_initial_defaults({'invoice_number': None, 'location': None}, reviewed)
        self.assertEqual(reviewed, {'invoice_number': 'MANUAL-1', 'location': 'Mumbai'})
        create.assert_not_called()


class OCRTemplateDefaultValueTests(SimpleTestCase):
    def test_defaults_override_ai_values_for_header_and_line_fields(self):
        template = {
            "standard_fields": ["location", "currency", "quantity"],
            "standard_field_overrides": {
                "location": {"default_value": "Pune", "scope": "header"},
                "currency": {"default_value": "INR", "scope": "header"},
                "quantity": {"default_value": "1", "scope": "line"},
            },
            "custom_fields": [],
        }
        extracted = {
            "location": None,
            "currency": "USD",
            "line_items": [
                {"item": "Service A", "quantity": None},
                {"item": "Service B", "quantity": 2},
            ],
        }

        result = _apply_template_default_values(extracted, template)

        self.assertEqual(result["location"], "Pune")
        self.assertEqual(result["currency"], "INR")
        self.assertEqual(result["line_items"][0]["quantity"], 1)
        self.assertEqual(result["line_items"][1]["quantity"], 1)

    def test_invalid_default_value_is_rejected_when_template_is_saved(self):
        with self.assertRaisesMessage(ValueError, 'Default Value for field "invoice_date"'):
            resolve_field_config({
                "standard_fields": ["invoice_date"],
                "standard_field_overrides": {
                    "invoice_date": {"default_value": "not-a-date"},
                },
                "custom_fields": [],
            })


class OCRDateFallbackPromptTests(SimpleTestCase):
    def test_single_date_fallback_uses_supplied_email_received_date(self):
        prompt = build_prompt(
            {"invoice_date": "Invoice date", "due_date": "Due date"},
            {},
            False,
            {"invoice_date": "date", "due_date": "date"},
            {},
            fallback_invoice_date="2026-10-27",
        )

        self.assertIn("Preserve that source date as `due_date`", prompt)
        self.assertIn("set `invoice_date` to `2026-10-27`", prompt)
        self.assertIn("never overwrite an explicitly stated date", prompt)

    def test_single_date_fallback_is_omitted_without_both_date_fields(self):
        prompt = build_prompt(
            {"invoice_date": "Invoice date"},
            {},
            False,
            {"invoice_date": "date"},
            {},
        )

        self.assertNotIn("Single-date fallback", prompt)


class OCREmailReceivedDateFallbackTests(SimpleTestCase):
    def test_missing_invoice_date_uses_email_received_date(self):
        from ocr.notebook_extraction_service import _apply_email_received_date_fallback

        data = {"invoice_date": None, "due_date": "2026-11-06"}
        result = _apply_email_received_date_fallback(
            data,
            ("invoice_date", "due_date"),
            email_received_at=datetime(2026, 10, 27, 12, 34),
        )

        self.assertEqual(result["invoice_date"], "2026-10-27")
        self.assertEqual(result["due_date"], "2026-11-06")

    def test_existing_invoice_date_is_never_overwritten(self):
        from ocr.notebook_extraction_service import _apply_email_received_date_fallback

        data = {"invoice_date": "2026-10-20"}
        result = _apply_email_received_date_fallback(
            data,
            ("invoice_date",),
            email_received_at=datetime(2026, 10, 27, 12, 34),
        )

        self.assertEqual(result["invoice_date"], "2026-10-20")


class OCRPostingRetrySafetyTests(SimpleTestCase):
    def test_confirmed_input_rejections_are_excluded(self):
        from netsuite.models import blocking_ocr_postings
        from django.db.models import Q
        queryset = Mock()
        self.assertIs(blocking_ocr_postings(queryset), queryset.exclude.return_value)
        queryset.exclude.assert_called_once_with(
            Q(error_message__contains='Please enter value(s) for:')
            | Q(error_message__contains='You have entered an Invalid Field Value'),
            status='error',
            netsuite_record_id__isnull=True,
            error_message__startswith='NetSuite rejected request (400) for record/v1/vendorBill:',
        )


class OCRPostedCopyTests(SimpleTestCase):
    def test_posted_record_uses_copy_path(self):
        from ocr.views import OCRReviewSaveView
        document = Mock()
        latest = document.versions.order_by.return_value.first.return_value
        document.netsuite_postings.filter.return_value.exists.return_value = True
        query = Mock()
        query.select_for_update.return_value.get.return_value = document
        user = Mock()
        with patch('ocr.views.transaction.atomic', return_value=nullcontext()), \
             patch('ocr.views._visible_document_queryset', return_value=query), \
             patch.object(OCRReviewSaveView, '_copy_posted_document', return_value='copy') as copy, \
             patch('ocr.views.persist_extraction') as persist:
            result = OCRReviewSaveView()._save_existing_document(user, 'id', {'invoice_number': 'new'})
        self.assertEqual(result, 'copy')
        copy.assert_called_once_with(user, document, latest, {'invoice_number': 'new'})
        persist.assert_not_called()

    def test_unposted_record_updates_existing_document(self):
        from ocr.views import OCRReviewSaveView
        document = Mock(upload_id=None)
        document.versions.order_by.return_value.first.return_value.normalized_json = {}
        document.netsuite_postings.filter.return_value.exists.return_value = False
        query = Mock()
        query.select_for_update.return_value.get.return_value = document
        version = Mock(version_number=2, reviewed_json={'invoice_number': 'edited'})
        user = Mock()
        with patch('ocr.views.transaction.atomic', return_value=nullcontext()), \
             patch('ocr.views._visible_document_queryset', return_value=query), \
             patch('ocr.views._is_company_admin', return_value=False), \
             patch('ocr.views.persist_extraction', return_value=(document, version)) as persist:
            OCRReviewSaveView()._save_existing_document(user, 'id', {'invoice_number': 'edited'})
        self.assertIs(persist.call_args.kwargs['document'], document)


class OCRHistoryDeletionVersionTests(SimpleTestCase):
    def test_deletion_checks_only_latest_version(self):
        from ocr.views import _prepare_history_deletion
        old = Mock(id='old', version_number=1, original_document=None, processed_document=None)
        current = Mock(id='current', version_number=2, original_document=None, processed_document=None)
        document = Mock()
        document.versions.all.return_value = [old, current]
        upload = Mock(document=document, file=None)
        batch = Mock()
        batch.uploads.all.return_value = [upload]
        batch.documents.filter.return_value = []
        queryset = Mock()
        queryset.prefetch_related.return_value.get.return_value = batch
        with patch('ocr.views._visible_batch_queryset', return_value=queryset), \
             patch('ocr.views.NetSuiteOCRPosting.objects.filter') as postings:
            postings.return_value.exists.return_value = False
            _prepare_history_deletion(user=Mock(), record_id='batch', record_type='batch')
        postings.assert_called_once_with(version_id__in=['current'], status='posted')

    def test_current_posted_version_is_protected(self):
        from ocr.views import _prepare_history_deletion
        document = Mock()
        document.versions.all.return_value = [Mock(id='current', version_number=2)]
        batch = Mock()
        batch.uploads.all.return_value = [Mock(document=document)]
        batch.documents.filter.return_value = []
        queryset = Mock()
        queryset.prefetch_related.return_value.get.return_value = batch
        with patch('ocr.views._visible_batch_queryset', return_value=queryset), \
             patch('ocr.views.NetSuiteOCRPosting.objects.filter') as postings:
            postings.return_value.exists.return_value = True
            with self.assertRaisesMessage(ValueError, 'Posted OCR history records cannot be deleted.'):
                _prepare_history_deletion(user=Mock(), record_id='batch', record_type='batch')


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
