"""Tests for the invoice module."""

from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from django.core.files.uploadedfile import SimpleUploadedFile

from tenancy.models import Company
from accounts.models import User
from invoice.models import InvoiceBatch, InvoiceFile, ExtractedInvoice, InvoiceNetSuiteMapping, FileStatus
from invoice.validators import InvoiceValidator


def _auth_header(user):
    from rest_framework_simplejwt.tokens import RefreshToken
    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}


def _make_user(**overrides):
    n = _next_id()
    defaults = {
        'email': f'user{n}@example.com',
        'first_name': 'Test',
        'last_name': 'User',
        'mobile_number': f'+1555{n:08d}',
        'is_active': True,
        'is_email_verified': True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password('testpass123')
    user.save()
    return user


_counter = 0

def _next_id():
    global _counter
    _counter += 1
    return _counter


class InvoiceValidatorTests(TestCase):
    def test_valid_invoice_passes(self):
        validator = InvoiceValidator()
        data = {
            'vendor': 'Test Vendor',
            'invoice_number': 'INV-001',
            'invoice_date': '2024-01-01',
            'currency': 'USD',
            'total_amount': '100.00',
            'tax_amount': '10.00',
            'subtotal': '90.00',
        }
        errors = validator.validate(data)
        self.assertEqual(len(errors), 0)

    def test_missing_required_field_fails(self):
        validator = InvoiceValidator()
        data = {
            'invoice_number': 'INV-001',
            'invoice_date': '2024-01-01',
            'currency': 'USD',
            'total_amount': '100.00',
        }
        errors = validator.validate(data)
        self.assertTrue(any(e.field == 'vendor' for e in errors))

    def test_invalid_currency_length_fails(self):
        validator = InvoiceValidator()
        data = {
            'vendor': 'Test Vendor',
            'invoice_number': 'INV-001',
            'invoice_date': '2024-01-01',
            'currency': 'USDD',
            'total_amount': '100.00',
        }
        errors = validator.validate(data)
        self.assertTrue(any(e.field == 'currency' for e in errors))

    def test_totals_mismatch_fails(self):
        validator = InvoiceValidator()
        data = {
            'vendor': 'Test Vendor',
            'invoice_number': 'INV-001',
            'invoice_date': '2024-01-01',
            'currency': 'USD',
            'total_amount': '100.00',
            'tax_amount': '10.00',
            'subtotal': '80.00',
        }
        errors = validator.validate(data)
        self.assertTrue(any(e.field == 'total_amount' for e in errors))


class InvoiceUploadTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name='Test Co',
            code='TC',
            status=Company.Status.ACTIVE,
        )
        self.user = _make_user(company=self.company)
        print('SETUP USER company:', self.user.company, 'company_id:', self.user.company_id)

    def _make_file(self, name='test.pdf', content=b'%PDF-1.4'):
        return SimpleUploadedFile(name, content, content_type='application/pdf')

    def test_upload_creates_batch(self):
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post('/api/v1/invoice/upload/', {
            'files': [self._make_file()],
        }, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(response.data['data']['total_files'], 1)


class InvoiceReviewTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.company = Company.objects.create(
            name='Test Co',
            code='TC',
            status=Company.Status.ACTIVE,
        )
        self.user = _make_user(company=self.company)
        self.batch = InvoiceBatch.objects.create(
            company=self.company,
            uploaded_by=self.user,
            total_files=1,
            processed_files=0,
            failed_files=0,
        )
        self.file = InvoiceFile.objects.create(
            batch=self.batch,
            uploaded_file=self._make_file(),
            original_filename='test.pdf',
            file_type='pdf',
            file_size=100,
        )
        self.extraction = ExtractedInvoice.objects.create(
            invoice_file=self.file,
            extracted_json={
                'vendor': 'Test Vendor',
                'invoice_number': 'INV-001',
                'invoice_date': '2024-01-01',
                'currency': 'USD',
                'total_amount': '100.00',
                'tax_amount': '10.00',
                'subtotal': '90.00',
            },
            confidence_score=0.95,
            extraction_status='COMPLETED',
        )

    def _make_file(self, name='test.pdf', content=b'%PDF-1.4'):
        return SimpleUploadedFile(name, content, content_type='application/pdf')

    def test_approve_valid_invoice(self):
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(f'/api/v1/invoice/review/{self.file.id}/', {
            'action': 'approve',
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.file.refresh_from_db()
        self.assertEqual(self.file.status, FileStatus.APPROVED)

    def test_approve_invalid_invoice_fails(self):
        self.extraction.extracted_json = {'vendor': 'Test'}
        self.extraction.save()
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(f'/api/v1/invoice/review/{self.file.id}/', {
            'action': 'approve',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('Validation failed', response.data['detail'])


class InvoiceNetSuiteMappingTests(TestCase):
    def test_create_mapping(self):
        mapping = InvoiceNetSuiteMapping.objects.create(
            invoice_field='vendor',
            netsuite_field='entity',
            is_required=True,
        )
        self.assertEqual(str(mapping), 'vendor → entity')
