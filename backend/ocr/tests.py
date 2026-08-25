"""
Test suite for the OCR application.

Phase 3 covers:
- Model (OCRUpload creation, new fields: file_hash, extension, processing metadata)
- Upload API (success 201, invalid MIME, large file, unauthorized, response includes hash/extension)
- Storage (file persisted on disk, unique filenames, path safety, content matches)
- Validators (file size, extension, MIME type, utility functions)
- Serializer (UploadSerializer, UploadResponseSerializer with new fields)
- Service (OCRService.upload with SHA256, extension, transaction safety)
- PDF Processor (single page, multi page, invalid PDF, corrupted PDF, 100+ pages, cleanup)

All tests are self-contained and use Django's test client with
SimpleJWT authentication, matching the pattern in accounts/tests.py.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import uuid
from pathlib import Path
import cv2
import numpy as np
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APITestCase, APIClient
from unittest.mock import MagicMock

from ocr.exceptions import (
    GeminiConnectionException,
    GeminiRateLimitException,
    GeminiTimeoutException,
    GeminiValidationException,
    InvalidFileException,
    PDFProcessingException,
    PDFTooLargeException,
    ImageProcessingException,
    InvalidImageException,
    OCRExtractionFailedException,
    OCRServiceException,
    UnsupportedFormatException,
)
from ocr.gemini_client import GeminiClient
from ocr.prompts import EXTRACTION_PROMPT, REVIEW_PROMPT,SYSTEM_PROMPT
from ocr.schema import validate_extraction_result
from ocr.image_processor import ImageProcessor, ImageQualityReport
from ocr.models import OCRUpload
from ocr.pdf_processor import MAX_PAGES, PDFProcessor
from ocr.serializers import UploadResponseSerializer, UploadSerializer
from ocr.services import OCRService
from ocr.validators import (
    ALLOWED_EXTENSIONS,
    ALLOWED_MIME_TYPES,
    MAX_FILE_SIZE,
    MIME_TYPE_TO_EXTENSION,
    get_extension_from_filename,
    get_extension_from_mime_type,
    validate_extension,
    validate_file_size,
    validate_mime_type,
)

User = get_user_model()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _next_id() -> int:
    """Global counter for unique emails across tests."""
    _next_id._counter = getattr(_next_id, '_counter', 0) + 1
    return _next_id._counter


def _make_user(**overrides) -> User:
    """Create a verified, active user with sensible defaults."""
    n = _next_id()
    defaults = {
        'email': f'ocr-user{n}@example.com',
        'first_name': 'OCR',
        'last_name': 'Tester',
        'is_active': True,
        'is_email_verified': True,
    }
    defaults.update(overrides)
    user = User(**defaults)
    user.set_password('testpass123')
    user.save()
    return user


def _auth_header(user: User) -> dict:
    """Return a Bearer token header for ``user`` using SimpleJWT."""
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    return {'HTTP_AUTHORIZATION': f'Bearer {str(refresh.access_token)}'}


def _make_pdf(content: bytes = b'%PDF-1.4 test content') -> SimpleUploadedFile:
    return SimpleUploadedFile(
        'invoice.pdf',
        content,
        content_type='application/pdf',
    )


def _make_png(content: bytes = b'\x89PNG\r\n\x1a\n') -> SimpleUploadedFile:
    return SimpleUploadedFile(
        'invoice.png',
        content,
        content_type='image/png',
    )


def _make_real_png() -> SimpleUploadedFile:
    from PIL import Image
    import io
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    return SimpleUploadedFile(
        'invoice.png',
        buffer.getvalue(),
        content_type='image/png',
    )


def _make_txt(content: bytes = b'plain text') -> SimpleUploadedFile:
    return SimpleUploadedFile(
        'invoice.txt',
        content,
        content_type='text/plain',
    )


def _make_invalid_file(content: bytes = b'invalid binary content') -> SimpleUploadedFile:
    return SimpleUploadedFile(
        'invoice.doc',
        content,
        content_type='application/msword',
    )


def _create_real_pdf(page_count: int = 1) -> bytes:
    """
    Create a real, valid PDF with the given number of pages using PyMuPDF.

    Args:
        page_count: Number of pages to generate.

    Returns:
        The PDF content as bytes.
    """
    import fitz

    doc = fitz.open()
    for _ in range(page_count):
        page = doc.new_page()
        page.insert_text((50, 50), 'Test Invoice')
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def _create_corrupted_pdf() -> bytes:
    """Return bytes that look like a PDF header but are corrupted."""
    return b'%PDF-1.4 \x00\x01\x02 corrupted content'


# ==================================================================
# Validator Tests
# ==================================================================

class ValidateFileSizeTests(TestCase):
    """Tests for ocr.validators.validate_file_size."""

    def test_valid_size(self):
        validate_file_size(1024)

    def test_exact_limit(self):
        validate_file_size(MAX_FILE_SIZE)

    def test_over_limit(self):
        with self.assertRaises(InvalidFileException):
            validate_file_size(MAX_FILE_SIZE + 1)

    def test_zero_size(self):
        validate_file_size(0)


class ValidateExtensionTests(TestCase):
    """Tests for ocr.validators.validate_extension."""

    def test_valid_extensions(self):
        for ext in ALLOWED_EXTENSIONS:
            validate_extension(f'invoice.{ext}')

    def test_case_insensitive(self):
        validate_extension('INVOICE.PDF')
        validate_extension('Invoice.PdF')

    def test_invalid_extension(self):
        with self.assertRaises(InvalidFileException):
            validate_extension('invoice.doc')

    def test_no_extension(self):
        with self.assertRaises(InvalidFileException):
            validate_extension('invoice')

    def test_empty_filename(self):
        with self.assertRaises(InvalidFileException):
            validate_extension('')


class ValidateMimeTypeTests(TestCase):
    """Tests for ocr.validators.validate_mime_type."""

    def test_valid_mime_types(self):
        for mime_type in ALLOWED_MIME_TYPES:
            validate_mime_type(mime_type)

    def test_invalid_mime_type(self):
        with self.assertRaises(InvalidFileException):
            validate_mime_type('application/msword')

    def test_empty_mime_type(self):
        with self.assertRaises(InvalidFileException):
            validate_mime_type('')

    def test_mime_to_extension_mapping(self):
        for mime_type, ext in MIME_TYPE_TO_EXTENSION.items():
            self.assertIn(ext, ALLOWED_EXTENSIONS)


class ValidatorUtilityTests(TestCase):
    """Tests for ocr.validators utility functions."""

    def test_get_extension_from_filename(self):
        self.assertEqual(get_extension_from_filename('invoice.pdf'), 'pdf')
        self.assertEqual(get_extension_from_filename('INVOICE.PDF'), 'pdf')
        self.assertEqual(get_extension_from_filename('photo.JPEG'), 'jpeg')

    def test_get_extension_from_filename_no_extension(self):
        with self.assertRaises(InvalidFileException):
            get_extension_from_filename('invoice')

    def test_get_extension_from_filename_empty(self):
        with self.assertRaises(InvalidFileException):
            get_extension_from_filename('')

    def test_get_extension_from_mime_type(self):
        self.assertEqual(
            get_extension_from_mime_type('application/pdf'), 'pdf'
        )
        self.assertEqual(
            get_extension_from_mime_type('image/png'), 'png'
        )

    def test_get_extension_from_mime_type_invalid(self):
        with self.assertRaises(InvalidFileException):
            get_extension_from_mime_type('application/msword')


# ==================================================================
# Serializer Tests
# ==================================================================

class UploadSerializerTests(TestCase):
    """Tests for ocr.serializers.UploadSerializer."""

    def test_valid_pdf(self):
        serializer = UploadSerializer(data={'file': _make_pdf()})
        self.assertTrue(serializer.is_valid())

    def test_valid_png(self):
        serializer = UploadSerializer(data={'file': _make_real_png()})
        self.assertTrue(serializer.is_valid())

    def test_missing_file(self):
        serializer = UploadSerializer(data={})
        self.assertFalse(serializer.is_valid())
        self.assertIn('file', serializer.errors)

    def test_invalid_extension(self):
        serializer = UploadSerializer(data={'file': _make_invalid_file()})
        self.assertFalse(serializer.is_valid())

    def test_invalid_mime_type(self):
        """A .pdf filename with an application/msword MIME type should fail."""
        file = SimpleUploadedFile(
            'invoice.pdf',
            b'text content',
            content_type='application/msword',
        )
        serializer = UploadSerializer(data={'file': file})
        with self.assertRaises(UnsupportedFormatException):
            serializer.is_valid()


class UploadResponseSerializerTests(TestCase):
    """Tests for ocr.serializers.UploadResponseSerializer."""

    def test_serializes_upload(self):
        user = _make_user()
        upload = OCRUpload.objects.create(
            user=user,
            original_filename='invoice.pdf',
            stored_filename='abc123.pdf',
            file=SimpleUploadedFile('abc123.pdf', b'%PDF-1.4'),
            file_size=100,
            mime_type='application/pdf',
            extension='pdf',
            file_hash='a' * 64,
            status=OCRUpload.Status.UPLOADED,
        )
        serializer = UploadResponseSerializer(upload)
        data = serializer.data
        self.assertEqual(data['upload_id'], str(upload.id))
        self.assertEqual(data['status'], 'UPLOADED')
        self.assertEqual(data['filename'], 'invoice.pdf')
        self.assertEqual(data['size'], 100)
        self.assertEqual(data['extension'], 'pdf')
        self.assertEqual(data['file_hash'], 'a' * 64)


# ==================================================================
# Model Tests
# ==================================================================

class OCRUploadModelTests(TestCase):
    """Tests for ocr.models.OCRUpload."""

    def test_create_upload(self):
        user = _make_user()
        upload = OCRUpload.objects.create(
            user=user,
            original_filename='invoice.pdf',
            stored_filename='abc123.pdf',
            file=SimpleUploadedFile('abc123.pdf', b'%PDF-1.4'),
            file_size=100,
            mime_type='application/pdf',
            extension='pdf',
            file_hash='a' * 64,
        )
        self.assertIsNotNone(upload.id)
        self.assertEqual(upload.status, OCRUpload.Status.UPLOADED)
        self.assertEqual(upload.original_filename, 'invoice.pdf')
        self.assertEqual(upload.mime_type, 'application/pdf')
        self.assertEqual(upload.file_size, 100)
        self.assertEqual(upload.extension, 'pdf')
        self.assertEqual(upload.file_hash, 'a' * 64)

    def test_str_representation(self):
        user = _make_user()
        upload = OCRUpload.objects.create(
            user=user,
            original_filename='invoice.pdf',
            stored_filename='abc123.pdf',
            file=SimpleUploadedFile('abc123.pdf', b'%PDF-1.4'),
            file_size=100,
            mime_type='application/pdf',
            extension='pdf',
            file_hash='a' * 64,
        )
        self.assertIn('invoice.pdf', str(upload))
        self.assertIn(str(upload.id), str(upload))

    def test_status_choices(self):
        choices = dict(OCRUpload.Status.choices)
        self.assertIn('UPLOADED', choices)
        self.assertIn('PROCESSING', choices)
        self.assertIn('COMPLETED', choices)
        self.assertIn('FAILED', choices)

    def test_processing_metadata_defaults_to_none(self):
        user = _make_user()
        upload = OCRUpload.objects.create(
            user=user,
            original_filename='invoice.pdf',
            stored_filename='abc123.pdf',
            file=SimpleUploadedFile('abc123.pdf', b'%PDF-1.4'),
            file_size=100,
            mime_type='application/pdf',
            extension='pdf',
            file_hash='a' * 64,
        )
        self.assertIsNone(upload.processing_started_at)
        self.assertIsNone(upload.processing_completed_at)
        self.assertIsNone(upload.processing_duration_ms)
        self.assertIsNone(upload.failure_reason)

    def test_user_related_name(self):
        user = _make_user()
        upload = OCRUpload.objects.create(
            user=user,
            original_filename='invoice.pdf',
            stored_filename='abc123.pdf',
            file=SimpleUploadedFile('abc123.pdf', b'%PDF-1.4'),
            file_size=100,
            mime_type='application/pdf',
            extension='pdf',
            file_hash='a' * 64,
        )
        self.assertIn(upload, user.ocr_uploads.all())

    def test_cascade_delete(self):
        user = _make_user()
        OCRUpload.objects.create(
            user=user,
            original_filename='invoice.pdf',
            stored_filename='abc123.pdf',
            file=SimpleUploadedFile('abc123.pdf', b'%PDF-1.4'),
            file_size=100,
            mime_type='application/pdf',
            extension='pdf',
            file_hash='a' * 64,
        )
        user.delete()
        self.assertEqual(OCRUpload.objects.count(), 0)


# ==================================================================
# Service Tests
# ==================================================================

class OCRServiceTests(TestCase):
    """Tests for ocr.services.OCRService."""

    def setUp(self):
        self.service = OCRService()
        self.user = _make_user()

    def test_upload_success(self):
        file = _make_pdf()
        upload = self.service.upload(file=file, user=self.user)
        self.assertIsNotNone(upload.id)
        self.assertEqual(upload.user, self.user)
        self.assertEqual(upload.original_filename, 'invoice.pdf')
        self.assertEqual(upload.status, OCRUpload.Status.UPLOADED)
        self.assertEqual(upload.mime_type, 'application/pdf')
        self.assertEqual(upload.extension, 'pdf')

    def test_upload_computes_sha256_hash(self):
        """The upload should compute and store a SHA256 hash."""
        content = b'%PDF-1.4 test content'
        file = _make_pdf(content)
        upload = self.service.upload(file=file, user=self.user)
        expected_hash = hashlib.sha256(content).hexdigest()
        self.assertEqual(upload.file_hash, expected_hash)
        self.assertEqual(len(upload.file_hash), 64)

    def test_upload_stores_extension(self):
        """The upload should store the canonical extension."""
        file = _make_pdf()
        upload = self.service.upload(file=file, user=self.user)
        self.assertEqual(upload.extension, 'pdf')

    def test_upload_generates_unique_filename(self):
        file1 = _make_pdf()
        file2 = _make_pdf()
        upload1 = self.service.upload(file=file1, user=self.user)
        upload2 = self.service.upload(file=file2, user=self.user)
        self.assertNotEqual(upload1.stored_filename, upload2.stored_filename)

    def test_upload_stored_filename_not_original(self):
        file = _make_pdf()
        upload = self.service.upload(file=file, user=self.user)
        self.assertNotEqual(upload.stored_filename, upload.original_filename)

    def test_upload_invalid_extension(self):
        file = _make_invalid_file()
        with self.assertRaises(InvalidFileException):
            self.service.upload(file=file, user=self.user)

    def test_upload_invalid_mime_type(self):
        """A .pdf filename with an application/msword MIME type should fail."""
        file = SimpleUploadedFile(
            'invoice.pdf',
            b'text content',
            content_type='application/msword',
        )
        with self.assertRaises(InvalidFileException):
            self.service.upload(file=file, user=self.user)

    def test_upload_oversized_file(self):
        """A file exceeding the format-specific limit should fail."""
        large_content = b'\x00' * (MAX_FILE_SIZE + 1)
        file = SimpleUploadedFile(
            'invoice.xlsx',
            large_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        with self.assertRaises(InvalidFileException):
            self.service.upload(file=file, user=self.user)

    def test_extract_delegates_to_extraction_service(self):
        """``extract`` should delegate, not raise NotImplementedError."""
        from unittest.mock import MagicMock, patch

        upload = self.service.upload(file=_make_pdf(), user=self.user)
        mock_extractor = MagicMock()
        mock_extractor.extract.return_value = {'status': 'COMPLETED', 'data': {}}
        self.service._extraction_service = mock_extractor
        result = self.service.extract(upload_id=upload.id, user=self.user)
        mock_extractor.extract.assert_called_once()
        self.assertEqual(result['status'], 'COMPLETED')

    def test_save_result_delegates_to_pipeline(self):
        """``save_result`` should delegate to the IDP pipeline."""
        from unittest.mock import MagicMock, patch

        upload = self.service.upload(file=_make_pdf(), user=self.user)
        with patch('ocr.services.ocr_service.idp_pipeline_service') as mock_pipeline:
            mock_pipeline.process_upload.return_value = {'document_id': 'doc-1'}
            result = self.service.save_result(
                upload_id=upload.id, result={}, user=self.user
            )
            mock_pipeline.process_upload.assert_called_once()
            self.assertEqual(result['document_id'], 'doc-1')


# ==================================================================
# Storage Tests
# ==================================================================

class StorageTests(TestCase):
    """Tests for file storage on disk."""

    def setUp(self):
        self.service = OCRService()
        self.user = _make_user()

    def test_file_persisted_on_disk(self):
        """The uploaded file should exist in MEDIA_ROOT/ocr/."""
        file = _make_pdf(b'%PDF-1.4 unique content')
        upload = self.service.upload(file=file, user=self.user)
        self.assertTrue(upload.file.storage.exists(upload.file.name))

    def test_file_content_matches(self):
        """The stored file content should match the uploaded content."""
        content = b'%PDF-1.4 unique content'
        file = _make_pdf(content)
        upload = self.service.upload(file=file, user=self.user)
        upload.file.open('rb')
        stored_content = upload.file.read()
        upload.file.close()
        self.assertEqual(stored_content, content)

    def test_unique_filenames_no_collision(self):
        """Two uploads with the same original filename get different paths."""
        file1 = _make_pdf()
        file2 = _make_pdf()
        upload1 = self.service.upload(file=file1, user=self.user)
        upload2 = self.service.upload(file=file2, user=self.user)
        self.assertNotEqual(upload1.file.name, upload2.file.name)

    def test_stored_filename_uses_uuid(self):
        """The stored filename should be a UUID hex, not the original."""
        file = _make_pdf()
        upload = self.service.upload(file=file, user=self.user)
        basename = os.path.basename(upload.file.name)
        name_part = basename.rsplit('.', 1)[0]
        self.assertEqual(len(name_part), 32)


# ==================================================================
# Endpoint Tests
# ==================================================================

class UploadEndpointTests(APITestCase):
    """Tests for POST /api/v1/ocr/upload/."""

    def setUp(self):
        self.client = APIClient()
        self.user = _make_user()

    def test_upload_success(self):
        """A valid PDF should get HTTP 201 with upload metadata."""
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(
            '/api/v1/ocr/upload/',
            {'file': _make_pdf()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['success'])
        self.assertEqual(
            response.data['message'], 'Upload accepted. Processing has been queued.'
        )
        data = response.data['data']
        self.assertIn('upload_id', data)
        self.assertEqual(data['status'], 'UPLOADED')
        self.assertEqual(data['filename'], 'invoice.pdf')
        self.assertIn('size', data)
        self.assertEqual(data['extension'], 'pdf')
        self.assertIn('file_hash', data)
        self.assertEqual(len(data['file_hash']), 64)

    def test_upload_png_success(self):
        """A valid PNG should get HTTP 201."""
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(
            '/api/v1/ocr/upload/',
            {'file': _make_real_png()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_upload_requires_auth(self):
        """
        Unauthenticated requests should be rejected.

        DRF returns 403 (not 401) because ``CookieJWTAuthentication``
        does not define ``authenticate_header()``, so no
        ``WWW-Authenticate`` header is sent — DRF then downgrades
        ``NotAuthenticated`` from 401 to 403.
        """
        response = self.client.post(
            '/api/v1/ocr/upload/',
            {'file': _make_pdf()},
            format='multipart',
        )
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

    def test_upload_invalid_extension(self):
        """A .doc file should get 400."""
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(
            '/api/v1/ocr/upload/',
            {'file': _make_invalid_file()},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_invalid_mime_type(self):
        """A .pdf filename with an application/msword MIME type should get 415."""
        file = SimpleUploadedFile(
            'invoice.pdf',
            b'text content',
            content_type='application/msword',
        )
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(
            '/api/v1/ocr/upload/',
            {'file': file},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

    def test_upload_missing_file(self):
        """A request with no file should get 400."""
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(
            '/api/v1/ocr/upload/',
            {},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_oversized_file(self):
        """A file exceeding the format-specific limit should get 400."""
        large_content = b'\x00' * (MAX_FILE_SIZE + 1)
        file = SimpleUploadedFile(
            'invoice.xlsx',
            large_content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.client.credentials(**_auth_header(self.user))
        response = self.client.post(
            '/api/v1/ocr/upload/',
            {'file': file},
            format='multipart',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_upload_creates_db_record(self):
        """A successful upload should create an OCRUpload row."""
        self.client.credentials(**_auth_header(self.user))
        self.client.post(
            '/api/v1/ocr/upload/',
            {'file': _make_pdf()},
            format='multipart',
        )
        self.assertEqual(OCRUpload.objects.count(), 1)
        upload = OCRUpload.objects.first()
        self.assertEqual(upload.user, self.user)
        self.assertEqual(upload.status, OCRUpload.Status.UPLOADED)


# ==================================================================
# PDF Processor Tests
# ==================================================================

class PDFProcessorTests(TestCase):
    """Tests for ocr.pdf_processor.PDFProcessor."""

    def setUp(self):
        self.processor = PDFProcessor()
        self.upload_id = str(uuid.uuid4())

    def tearDown(self):
        self.processor.cleanup(self.upload_id)

    def _write_temp_pdf(self, content: bytes) -> Path:
        """Write bytes to a temporary file and return the path."""
        temp_dir = Path(tempfile.mkdtemp())
        pdf_path = temp_dir / 'test.pdf'
        pdf_path.write_bytes(content)
        return pdf_path

    def test_is_pdf_valid(self):
        """A real PDF should be identified as a valid PDF."""
        pdf_bytes = _create_real_pdf(page_count=1)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        self.assertTrue(self.processor.is_pdf(pdf_path))
        pdf_path.unlink()

    def test_is_pdf_invalid(self):
        """A non-PDF file should not be identified as a PDF."""
        txt_path = self._write_temp_pdf(b'not a pdf')
        self.assertFalse(self.processor.is_pdf(txt_path))
        txt_path.unlink()

    def test_get_page_count_single(self):
        """A single-page PDF should return page count 1."""
        pdf_bytes = _create_real_pdf(page_count=1)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        count = self.processor.get_page_count(pdf_path)
        self.assertEqual(count, 1)
        pdf_path.unlink()

    def test_get_page_count_multi(self):
        """A 5-page PDF should return page count 5."""
        pdf_bytes = _create_real_pdf(page_count=5)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        count = self.processor.get_page_count(pdf_path)
        self.assertEqual(count, 5)
        pdf_path.unlink()

    def test_get_page_count_corrupted(self):
        """A corrupted PDF should raise PDFProcessingException."""
        pdf_bytes = _create_corrupted_pdf()
        pdf_path = self._write_temp_pdf(pdf_bytes)
        with self.assertRaises(PDFProcessingException):
            self.processor.get_page_count(pdf_path)
        pdf_path.unlink()

    def test_convert_single_page_pdf(self):
        """A single-page PDF should produce one PNG image."""
        pdf_bytes = _create_real_pdf(page_count=1)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        images = self.processor.convert_to_images(pdf_path, self.upload_id)
        self.assertEqual(len(images), 1)
        self.assertTrue(all(p.suffix == '.png' for p in images))
        self.assertTrue(all(p.exists() for p in images))
        pdf_path.unlink()

    def test_convert_multi_page_pdf(self):
        """A 3-page PDF should produce 3 PNG images."""
        pdf_bytes = _create_real_pdf(page_count=3)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        images = self.processor.convert_to_images(pdf_path, self.upload_id)
        self.assertEqual(len(images), 3)
        self.assertTrue(all(p.exists() for p in images))
        for i, path in enumerate(images, 1):
            self.assertIn(f'page_{i:03d}', path.name)
        pdf_path.unlink()

    def test_convert_corrupted_pdf(self):
        """A corrupted PDF should raise PDFProcessingException."""
        pdf_bytes = _create_corrupted_pdf()
        pdf_path = self._write_temp_pdf(pdf_bytes)
        with self.assertRaises(PDFProcessingException):
            self.processor.convert_to_images(pdf_path, self.upload_id)
        pdf_path.unlink()

    def test_convert_too_many_pages(self):
        """A PDF with more than MAX_PAGES should raise PDFTooLargeException."""
        pdf_bytes = _create_real_pdf(page_count=MAX_PAGES + 1)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        with self.assertRaises(PDFTooLargeException):
            self.processor.convert_to_images(pdf_path, self.upload_id)
        pdf_path.unlink()

    def test_cleanup_removes_temporary_files(self):
        """Cleanup should delete the temporary directory and all images."""
        pdf_bytes = _create_real_pdf(page_count=2)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        images = self.processor.convert_to_images(pdf_path, self.upload_id)
        output_dir = images[0].parent
        self.assertTrue(output_dir.exists())
        self.processor.cleanup(self.upload_id)
        self.assertFalse(output_dir.exists())
        pdf_path.unlink()

    def test_cleanup_idempotent(self):
        """Cleanup should not raise if the directory doesn't exist."""
        self.processor.cleanup(self.upload_id)
        self.processor.cleanup(self.upload_id)

    def test_convert_images_are_rgb_png(self):
        """Converted images should be PNG files."""
        pdf_bytes = _create_real_pdf(page_count=1)
        pdf_path = self._write_temp_pdf(pdf_bytes)
        images = self.processor.convert_to_images(pdf_path, self.upload_id)
        from PIL import Image

        img = Image.open(images[0])
        self.assertEqual(img.format, 'PNG')
        img.close()
        pdf_path.unlink()

# ==================================================================
# Image Processor Tests
# ==================================================================

class ImageProcessorLoadSaveTests(TestCase):
    """Tests for ImageProcessor.load_image() and save_image()."""

    def setUp(self):
        self.processor = ImageProcessor()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_test_image(self, width: int = 100, height: int = 100) -> Path:
        image = np.zeros((height, width, 3), dtype=np.uint8)
        image[:] = (255, 255, 255)  # white
        path = self.temp_dir / 'test.png'
        cv2.imwrite(str(path), image)
        return path

    def test_load_image_valid(self):
        path = self._make_test_image()
        image = self.processor.load_image(path)
        self.assertIsInstance(image, np.ndarray)
        self.assertEqual(image.shape[0], 100)
        self.assertEqual(image.shape[1], 100)

    def test_load_image_not_found(self):
        with self.assertRaises(InvalidImageException):
            self.processor.load_image('/nonexistent/path.png')

    def test_load_image_corrupted(self):
        path = self.temp_dir / 'corrupted.png'
        path.write_bytes(b'not an image')
        with self.assertRaises(InvalidImageException):
            self.processor.load_image(path)

    def test_save_image(self):
        image = np.zeros((50, 50, 3), dtype=np.uint8)
        save_path = self.temp_dir / 'saved.png'
        result = self.processor.save_image(image, save_path)
        self.assertTrue(result.exists())
        self.assertEqual(result, save_path)


class ImageProcessorTransformTests(TestCase):
    """Tests for individual ImageProcessor transformation methods."""

    def setUp(self):
        self.processor = ImageProcessor()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_color_image(self) -> np.ndarray:
        """Create a 200x100 BGR image with a colored rectangle."""
        image = np.zeros((100, 200, 3), dtype=np.uint8)
        image[:] = (200, 150, 100)  # BGR
        cv2.rectangle(image, (20, 20), (180, 80), (50, 100, 200), -1)
        return image

    def test_convert_to_grayscale(self):
        image = self._make_color_image()
        gray = self.processor.convert_to_grayscale(image)
        self.assertEqual(len(gray.shape), 2)

    def test_convert_to_grayscale_already_gray(self):
        gray = np.zeros((50, 50), dtype=np.uint8)
        result = self.processor.convert_to_grayscale(gray)
        self.assertIs(result, gray)

    def test_remove_noise(self):
        image = self._make_color_image()
        denoised = self.processor.remove_noise(image)
        self.assertEqual(denoised.shape, image.shape)

    def test_adaptive_threshold(self):
        gray = np.ones((100, 200), dtype=np.uint8) * 200
        cv2.rectangle(gray, (20, 20), (180, 80), 50, -1)
        result = self.processor.adaptive_threshold(gray)
        self.assertEqual(len(result.shape), 2)

    def test_adaptive_threshold_requires_gray(self):
        color = self._make_color_image()
        with self.assertRaises(ImageProcessingException):
            self.processor.adaptive_threshold(color)

    def test_increase_contrast_grayscale(self):
        gray = np.ones((100, 100), dtype=np.uint8) * 128
        result = self.processor.increase_contrast(gray)
        self.assertEqual(result.shape, gray.shape)

    def test_increase_contrast_color(self):
        image = self._make_color_image()
        result = self.processor.increase_contrast(image)
        self.assertEqual(result.shape, image.shape)

    def test_deskew_no_skew(self):
        image = self._make_color_image()
        result = self.processor.deskew(image)
        self.assertEqual(result.shape[:2], image.shape[:2])

    def test_resize_for_ocr(self):
        image = np.zeros((100, 500, 3), dtype=np.uint8)
        result = self.processor.resize_for_ocr(image)
        self.assertEqual(result.shape[1], settings.OCR_TARGET_WIDTH)

    def test_resize_for_ocr_too_small(self):
        image = np.zeros((50, 50, 3), dtype=np.uint8)
        with self.assertRaises(InvalidImageException):
            self.processor.resize_for_ocr(image)

    def test_sharpen(self):
        image = self._make_color_image()
        result = self.processor.sharpen(image)
        self.assertEqual(result.shape, image.shape)

    def test_sharpen_zero_strength(self):
        with override_settings(OCR_SHARPEN_STRENGTH=0):
            image = self._make_color_image()
            result = self.processor.sharpen(image)
            self.assertIs(result, image)

    def test_detect_orientation_blank(self):
        image = np.zeros((100, 100, 3), dtype=np.uint8)
        angle = self.processor.detect_orientation(image)
        self.assertEqual(angle, 0.0)

    def test_auto_rotate_already_upright(self):
        image = self._make_color_image()
        result = self.processor.auto_rotate(image)
        self.assertEqual(result.shape, image.shape)


class ImageProcessorPipelineTests(TestCase):
    """Tests for the full preprocessing pipeline."""

    def setUp(self):
        self.processor = ImageProcessor()
        self.upload_id = str(uuid.uuid4())
        self.temp_dir = Path(tempfile.mkdtemp())
        self.output_dir = Path(settings.MEDIA_ROOT) / 'ocr' / 'processed' / self.upload_id

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir, ignore_errors=True)

    def _make_test_image(self, name: str = 'test.png',
                         width: int = 500, height: int = 400,
                         color: bool = True) -> Path:
        if color:
            image = np.zeros((height, width, 3), dtype=np.uint8)
            image[:] = (200, 150, 100)
            cv2.rectangle(image, (50, 50), (width - 50, height - 50), (50, 100, 200), -1)
        else:
            image = np.ones((height, width), dtype=np.uint8) * 200
            cv2.rectangle(image, (50, 50), (width - 50, height - 50), 50, -1)
        path = self.temp_dir / name
        cv2.imwrite(str(path), image)
        return path

    def test_pipeline_png(self):
        path = self._make_test_image('invoice.png')
        result = self.processor.preprocess(path, self.upload_id)
        self.assertTrue(result.exists())
        self.assertIn('_processed.png', result.name)

    def test_pipeline_jpeg(self):
        image = np.zeros((400, 500, 3), dtype=np.uint8)
        image[:] = (200, 150, 100)
        path = self.temp_dir / 'invoice.jpg'
        cv2.imwrite(str(path), image)
        result = self.processor.preprocess(path, self.upload_id)
        self.assertTrue(result.exists())

    def test_pipeline_webp(self):
        image = np.zeros((400, 500, 3), dtype=np.uint8)
        image[:] = (200, 150, 100)
        path = self.temp_dir / 'invoice.webp'
        cv2.imwrite(str(path), image)
        result = self.processor.preprocess(path, self.upload_id)
        self.assertTrue(result.exists())

    def test_pipeline_invalid_image(self):
        path = self.temp_dir / 'invalid.png'
        path.write_bytes(b'not an image')
        with self.assertRaises(InvalidImageException):
            self.processor.preprocess(path, self.upload_id)

    def test_pipeline_very_large_image(self):
        """A very large image (just below max) should still be processed."""
        path = self._make_test_image('large.png', width=2000, height=2000)
        result = self.processor.preprocess(path, self.upload_id)
        self.assertTrue(result.exists())
        # Should be resized to target width
        loaded = cv2.imread(str(result))
        self.assertEqual(loaded.shape[1], settings.OCR_TARGET_WIDTH)


class ImageQualityReportTests(TestCase):
    """Tests for ImageQualityReport."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _make_test_image(self, name: str = 'test.png') -> Path:
        image = np.zeros((200, 300, 3), dtype=np.uint8)
        image[:] = (100, 150, 200)
        path = self.temp_dir / name
        cv2.imwrite(str(path), image)
        return path

    def test_report_creation(self):
        path = self._make_test_image()
        report = ImageQualityReport.from_image(path)
        self.assertEqual(report.width, 300)
        self.assertEqual(report.height, 200)
        self.assertIsInstance(report.brightness, float)
        self.assertIsInstance(report.contrast, float)
        self.assertIsInstance(report.blur_score, float)
        self.assertIsInstance(report.noise_score, float)
        self.assertIsInstance(report.rotation_angle, float)
        self.assertIsInstance(report.processing_time_ms, float)

    def test_report_as_dict(self):
        path = self._make_test_image()
        report = ImageQualityReport.from_image(path)
        data = report.as_dict()
        self.assertEqual(data['width'], 300)
        self.assertEqual(data['height'], 200)
        self.assertIn('brightness', data)
        self.assertIn('contrast', data)
        self.assertIn('blur_score', data)
        self.assertIn('noise_score', data)
        self.assertIn('rotation_angle', data)
        self.assertIn('processing_time_ms', data)
        self.assertIn('path', data)
        self.assertIn('dpi', data)

    def test_report_dpi_none(self):
        """Images without DPI metadata should report None."""
        path = self._make_test_image()
        report = ImageQualityReport.from_image(path)
        self.assertIsNone(report.dpi)
        data = report.as_dict()
        self.assertIsNone(data['dpi'])

# ==================================================================
# Schema Validation Tests
# ==================================================================

class SchemaValidationTests(TestCase):
    """Tests for ocr.schema.validate_extraction_result."""

    def _valid_data(self) -> dict:
        return {
            'vendor': 'Acme Corp',
            'invoice_number': 'INV-001',
            'invoice_date': '2024-01-15',
            'currency': 'USD',
            'subtotal': 100.0,
            'tax': 10.0,
            'total': 110.0,
            'purchase_order': 'PO-001',
            'items': [
                {'description': 'Item 1', 'quantity': 1, 'unit_price': 100.0, 'total': 100.0}
            ],
            'confidence': {'vendor': 0.95},
        }

    def test_valid_data(self):
        data = self._valid_data()
        result = validate_extraction_result(data)
        self.assertEqual(result, data)

    def test_missing_key(self):
        data = self._valid_data()
        del data['vendor']
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_wrong_type_string(self):
        data = self._valid_data()
        data['vendor'] = 123
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_wrong_type_numeric(self):
        data = self._valid_data()
        data['subtotal'] = 'one hundred'
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_invalid_date_format(self):
        data = self._valid_data()
        data['invoice_date'] = '2024/01/15'
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_invalid_currency(self):
        data = self._valid_data()
        data['currency'] = 'US'
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_negative_total(self):
        data = self._valid_data()
        data['total'] = -1
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_items_not_list(self):
        data = self._valid_data()
        data['items'] = 'not a list'
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_item_missing_field(self):
        data = self._valid_data()
        data['items'] = [{'description': 'Item', 'quantity': 1}]
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_confidence_invalid_range(self):
        data = self._valid_data()
        data['confidence'] = {'vendor': 1.5}
        with self.assertRaises(GeminiValidationException):
            validate_extraction_result(data)

    def test_none_values_allowed(self):
        data = self._valid_data()
        data['vendor'] = None
        data['invoice_number'] = None
        result = validate_extraction_result(data)
        self.assertIsNone(result['vendor'])
        self.assertIsNone(result['invoice_number'])


# ==================================================================
# Prompt Tests
# ==================================================================

class PromptTests(TestCase):
    """Tests for ocr.prompts module-level constants."""

    def test_system_prompt_exists(self):
        self.assertIsInstance(SYSTEM_PROMPT, str)
        self.assertGreater(len(SYSTEM_PROMPT), 0)

    def test_extraction_prompt_exists(self):
        self.assertIsInstance(EXTRACTION_PROMPT, str)
        self.assertGreater(len(EXTRACTION_PROMPT), 0)

    def test_extraction_prompt_contains_required_fields(self):
        for field in ['vendor', 'invoice_number', 'invoice_date',
                      'currency', 'subtotal', 'tax', 'total',
                      'purchase_order', 'items', 'confidence']:
            self.assertIn(field, EXTRACTION_PROMPT)

    def test_extraction_prompt_no_markdown(self):
        """The extraction prompt should not contain markdown code blocks."""
        self.assertNotIn('```', EXTRACTION_PROMPT)

    def test_review_prompt_exists(self):
        self.assertIsInstance(REVIEW_PROMPT, str)
        self.assertGreater(len(REVIEW_PROMPT), 0)


# ==================================================================
# Gemini Client Tests (Mocked)
# ==================================================================

class GeminiClientParseResponseTests(TestCase):
    """Tests for GeminiClient._parse_response()."""

    def setUp(self):
        self.client = GeminiClient()

    def _valid_json_response(self) -> str:
        return (
            '{"vendor": "Acme", "invoice_number": "INV-001", '
            '"invoice_date": "2024-01-15", "currency": "USD", '
            '"subtotal": 100, "tax": 10, "total": 110, '
            '"purchase_order": "PO-001", "items": [], "confidence": {}}'
        )

    def test_parse_valid_json(self):
        result = self.client._parse_response('{}', 'abc123')
        self.assertIsInstance(result, dict)

    def test_parse_with_markdown_fence(self):
        text = '```json\n' + self._valid_json_response() + '\n```'
        result = self.client._parse_response(text, 'abc123')
        self.assertIn('vendor', result)

    def test_parse_invalid_json(self):
        with self.assertRaises(GeminiValidationException):
            self.client._parse_response('not json', 'abc123')

    def test_parse_empty_response(self):
        """Should be caught by _call_api, but _parse_response handles empty."""
        with self.assertRaises(GeminiValidationException):
            self.client._parse_response('', 'abc123')

    def test_parse_non_object_json(self):
        with self.assertRaises(GeminiValidationException):
            self.client._parse_response('[1, 2, 3]', 'abc123')


class GeminiClientExtractMockedTests(TestCase):
    """Tests for GeminiClient.extract() with mocked API calls."""

    def _patch_genai(self, mock_response_text: str):
        """Patch the genai library to return a mock response."""
        from unittest.mock import MagicMock, patch

        mock_genai = MagicMock()
        mock_genai.Client.return_value.models.generate_content.return_value = (
            MagicMock(text=mock_response_text)
        )
        mock_genai.types.Part.from_uri = MagicMock()
        return patch('ocr.gemini_client._genai', mock_genai)

    def test_extract_success(self):
        valid_json = (
            '{"vendor": "Acme", "invoice_number": "INV-001", '
            '"invoice_date": "2024-01-15", "currency": "USD", '
            '"subtotal": 100, "tax": 10, "total": 110, '
            '"purchase_order": "PO-001", "items": [], "confidence": {}}'
        )
        patcher = self._patch_genai(valid_json)
        patcher.start()
        try:
            client = GeminiClient()
            result = client.extract('/fake/path.png')
            self.assertIn('vendor', result)
            self.assertEqual(result['vendor'], 'Acme')
        finally:
            patcher.stop()

    def test_extract_invalid_json_retries_then_fails(self):
        """Should retry on invalid JSON and eventually fail."""
        patcher = self._patch_genai('not json at all')
        patcher.start()
        try:
            with override_settings(OCR_MAX_RETRIES=2):
                client = GeminiClient()
                client.max_retries = 2
                with self.assertRaises(GeminiValidationException):
                    client.extract('/fake/path.png')
        finally:
            patcher.stop()

    def test_extract_strips_markdown(self):
        valid_json = (
            '{"vendor": "Acme", "invoice_number": "INV-001", '
            '"invoice_date": "2024-01-15", "currency": "USD", '
            '"subtotal": 100, "tax": 10, "total": 110, '
            '"purchase_order": "PO-001", "items": [], "confidence": {}}'
        )
        text = '```json\n' + valid_json + '\n```'
        patcher = self._patch_genai(text)
        patcher.start()
        try:
            with override_settings(OCR_MAX_RETRIES=1, OCR_RETRY_DELAY=0):
                client = GeminiClient()
                client.max_retries = 1
                result = client.extract('/fake/path.png')
                self.assertIn('vendor', result)
        finally:
            patcher.stop()

    def test_extract_timeout_retries(self):
        """Should retry on timeout and eventually raise."""
        from unittest.mock import MagicMock, patch

        mock_genai = MagicMock()
        mock_genai.Client.return_value.models.generate_content.side_effect = (
            TimeoutError('Request timed out')
        )
        mock_genai.types.Part.from_uri = MagicMock()

        patcher = patch('ocr.gemini_client._genai', mock_genai)
        patcher.start()
        try:
            with override_settings(OCR_MAX_RETRIES=3, OCR_RETRY_DELAY=0):
                client = GeminiClient()
                client.max_retries = 3
                client.retry_delay = 0
                with self.assertRaises(GeminiTimeoutException):
                    client.extract('/fake/path.png')
        finally:
            patcher.stop()

    def test_extract_rate_limit_retries(self):
        """Should retry on 429 rate limit and eventually raise."""
        from unittest.mock import MagicMock, patch

        mock_genai = MagicMock()
        mock_genai.Client.return_value.models.generate_content.side_effect = (
            Exception('429 Too Many Requests')
        )
        mock_genai.types.Part.from_uri = MagicMock()

        patcher = patch('ocr.gemini_client._genai', mock_genai)
        patcher.start()
        try:
            with override_settings(OCR_MAX_RETRIES=2, OCR_RETRY_DELAY=0):
                client = GeminiClient()
                client.max_retries = 2
                client.retry_delay = 0
                with self.assertRaises(GeminiRateLimitException):
                    client.extract('/fake/path.png')
        finally:
            patcher.stop()

    def test_extract_connection_error_retries(self):
        """Should retry on connection error and eventually raise."""
        from unittest.mock import MagicMock, patch

        mock_genai = MagicMock()
        mock_genai.Client.return_value.models.generate_content.side_effect = (
            ConnectionError('Connection refused')
        )
        mock_genai.types.Part.from_uri = MagicMock()

        patcher = patch('ocr.gemini_client._genai', mock_genai)
        patcher.start()
        try:
            with override_settings(OCR_MAX_RETRIES=2, OCR_RETRY_DELAY=0):
                client = GeminiClient()
                client.max_retries = 2
                client.retry_delay = 0
                with self.assertRaises(GeminiConnectionException):
                    client.extract('/fake/path.png')
        finally:
            patcher.stop()


# ==================================================================
# Extraction Service Tests (Mocked Gemini)
# ==================================================================

class OCRExtractionServiceTests(TestCase):
    """Tests for ocr.extraction_service.OCRExtractionService."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.user = _make_user()
        # Create a real OCRUpload with an image file
        width, height = 300, 200
        image = np.zeros((height, width, 3), dtype=np.uint8)
        image[:] = (200, 150, 100)
        cv2.rectangle(image, (50, 50), (250, 150), (50, 100, 200), -1)
        img_path = self.temp_dir / 'test_invoice.png'
        cv2.imwrite(str(img_path), image)
        self.upload = OCRUpload.objects.create(
            user=self.user,
            original_filename='test_invoice.png',
            stored_filename='test_invoice.png',
            file=SimpleUploadedFile(
                'test_invoice.png', img_path.read_bytes(),
                content_type='image/png',
            ),
            file_size=img_path.stat().st_size,
            mime_type='image/png',
            extension='png',
            file_hash='b' * 64,
            status=OCRUpload.Status.UPLOADED,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _valid_extraction_result(self) -> dict:
        return {
            'vendor': 'Acme Corp',
            'invoice_number': 'INV-001',
            'invoice_date': '2024-01-15',
            'currency': 'USD',
            'subtotal': 100.0,
            'tax': 10.0,
            'total': 110.0,
            'purchase_order': 'PO-001',
            'items': [
                {'description': 'Widget', 'quantity': 2,
                 'unit_price': 50.0, 'total': 100.0}
            ],
            'confidence': {'vendor': 0.95, 'invoice_number': 0.98},
        }

    def _mock_gemini_client(self, result: dict | Exception):
        """Create a mock GeminiClient that returns the given result or raises."""
        from unittest.mock import MagicMock
        mock = MagicMock()
        if isinstance(result, Exception):
            mock.extract.side_effect = result
        else:
            mock.extract.return_value = result
        return mock

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_success(self):
        """A successful extraction should return a complete result dict."""
        from ocr.extraction_service import OCRExtractionService

        mock_client = self._mock_gemini_client(self._valid_extraction_result())
        service = OCRExtractionService(gemini_client=mock_client)
        result = service.extract(self.upload, self.user)

        self.assertEqual(result['status'], 'COMPLETED')
        self.assertIn('extraction_id', result)
        self.assertEqual(result['upload_id'], str(self.upload.id))
        self.assertIn('data', result)
        self.assertIn('confidence', result)
        self.assertIn('image_quality', result)
        self.assertIn('processing_time_ms', result)

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_disables_gemini(self):
        """Should raise when Gemini is disabled."""
        from ocr.extraction_service import OCRExtractionService

        service = OCRExtractionService(gemini_client=MagicMock())
        with override_settings(OCR_ENABLE_GEMINI=False):
            with self.assertRaises(OCRServiceException):
                service.extract(self.upload, self.user)

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_invalid_json_raises(self):
        """Should raise GeminiValidationException on invalid JSON."""
        from ocr.extraction_service import OCRExtractionService

        mock_client = self._mock_gemini_client(
            GeminiValidationException('bad json')
        )
        service = OCRExtractionService(gemini_client=mock_client)
        with self.assertRaises(GeminiValidationException):
            service.extract(self.upload, self.user)

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_timeout_raises(self):
        mock_client = self._mock_gemini_client(
            GeminiTimeoutException('timed out')
        )
        from ocr.extraction_service import OCRExtractionService
        service = OCRExtractionService(gemini_client=mock_client)
        with self.assertRaises(GeminiTimeoutException):
            service.extract(self.upload, self.user)

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_rate_limit_raises(self):
        mock_client = self._mock_gemini_client(
            GeminiRateLimitException('rate limited')
        )
        from ocr.extraction_service import OCRExtractionService
        service = OCRExtractionService(gemini_client=mock_client)
        with self.assertRaises(GeminiRateLimitException):
            service.extract(self.upload, self.user)

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_missing_fields(self):
        """Confidence should reflect missing fields."""
        from ocr.extraction_service import OCRExtractionService

        data = self._valid_extraction_result()
        data['vendor'] = None
        data['invoice_number'] = None
        mock_client = self._mock_gemini_client(data)
        service = OCRExtractionService(gemini_client=mock_client)
        result = service.extract(self.upload, self.user)

        self.assertIn('vendor', result['confidence']['missing_fields'])
        self.assertIn('invoice_number', result['confidence']['missing_fields'])
        self.assertEqual(
            result['confidence']['fields']['vendor'], 0.0
        )

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_low_confidence_fields(self):
        """Low confidence fields should be identified."""
        from ocr.extraction_service import OCRExtractionService

        data = self._valid_extraction_result()
        data['items'] = [{'description': '', 'quantity': 0, 'unit_price': 0, 'total': 0}]
        mock_client = self._mock_gemini_client(data)
        service = OCRExtractionService(gemini_client=mock_client)
        result = service.extract(self.upload, self.user)

        # Empty item fields should be flagged as low confidence
        self.assertIn('items', result['confidence']['low_confidence_fields'])

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_empty_items(self):
        """Empty items list should be flagged as missing/low confidence."""
        from ocr.extraction_service import OCRExtractionService

        data = self._valid_extraction_result()
        data['items'] = []
        mock_client = self._mock_gemini_client(data)
        service = OCRExtractionService(gemini_client=mock_client)
        result = service.extract(self.upload, self.user)
        self.assertIn('items', result['confidence']['missing_fields'])

    @override_settings(OCR_ENABLE_GEMINI=True)
    def test_extract_includes_image_quality(self):
        """Result should include image quality report."""
        from ocr.extraction_service import OCRExtractionService

        mock_client = self._mock_gemini_client(self._valid_extraction_result())
        service = OCRExtractionService(gemini_client=mock_client)
        result = service.extract(self.upload, self.user)
        quality = result['image_quality']
        self.assertIn('width', quality)
        self.assertIn('height', quality)
        self.assertIn('brightness', quality)
        self.assertIn('contrast', quality)
        self.assertIn('blur_score', quality)
        self.assertIn('noise_score', quality)
        self.assertIn('rotation_angle', quality)


# ==================================================================
# Confidence Calculation Tests
# ==================================================================

class ConfidenceCalculationTests(TestCase):
    """Test the _calculate_confidence static method."""

    def _call(self, data: dict) -> dict:
        from ocr.extraction_service import OCRExtractionService
        return OCRExtractionService._calculate_confidence(data)

    def _full_data(self) -> dict:
        return {
            'vendor': 'Acme',
            'invoice_number': 'INV-001',
            'invoice_date': '2024-01-15',
            'currency': 'USD',
            'subtotal': 100.0,
            'tax': 10.0,
            'total': 110.0,
            'purchase_order': 'PO-001',
            'items': [{'description': 'X', 'quantity': 1, 'unit_price': 100, 'total': 100}],
        }

    def test_all_present_high_confidence(self):
        result = self._call(self._full_data())
        self.assertGreater(result['overall'], 0.0)
        self.assertEqual(result['missing_fields'], [])

    def test_missing_field(self):
        data = self._full_data()
        data['vendor'] = None
        result = self._call(data)
        self.assertIn('vendor', result['missing_fields'])
        self.assertEqual(result['fields']['vendor'], 0.0)

    def test_zero_numeric_field(self):
        data = self._full_data()
        data['tax'] = 0
        result = self._call(data)
        self.assertEqual(result['fields']['tax'], 0.8)

    def test_empty_items(self):
        data = self._full_data()
        data['items'] = []
        result = self._call(data)
        self.assertIn('items', result['missing_fields'])
        self.assertEqual(result['fields']['items'], 0.0)

    def test_empty_string_field(self):
        data = self._full_data()
        data['vendor'] = ''
        result = self._call(data)
        self.assertIn('vendor', result['missing_fields'])
        self.assertEqual(result['fields']['vendor'], 0.0)
