"""
Document structural validation for the IDP engine.

Validates an uploaded file before any processing begins. Catches
corrupted files, unsupported formats, empty files, and structural
problems so the pipeline fails fast with a recoverable error. Also
provides business-rule validation for normalized extraction results.
"""

from __future__ import annotations

from pathlib import Path

from ocr.exceptions import InvalidFileException, PDFProcessingException
from ocr.pdf_processor import pdf_processor
from ocr.utils import logger
from ocr.validators import (
    validate_extension,
    validate_file_size,
    validate_mime_type,
)

#: Fields that must be present (non-null, non-empty) for a usable document.
#: Validation of these drives the REVIEW_REQUIRED status.
REQUIRED_FIELDS: tuple[str, ...] = (
    'vendor',
    'invoice_number',
    'invoice_date',
    'currency',
    'total',
)

#: Tolerance (absolute) for arithmetic checks on monetary fields.
MONEY_TOLERANCE: float = 0.02


class ValidationService:
    """
    Structural and business-rule validation for the IDP pipeline.

    Each method is isolated and independently testable. The pipeline
    calls ``validate()`` once at the start and
    ``validate_business_rules()`` after normalization.
    """

    def validate(self, *, file, mime_type: str, original_filename: str) -> dict:
        """
        Validate a candidate document file.

        Args:
            file: The uploaded file (has ``.name``, ``.size``,
                ``.content_type``).
            mime_type: The file's MIME type.
            original_filename: The original filename.

        Returns:
            A validation report dict with ``is_valid`` and ``errors``.

        Raises:
            InvalidFileException: On invalid extension/size/MIME.
            PDFProcessingException: If a PDF cannot be opened.
        """
        errors: list[str] = []

        # 1. Extension, size, MIME checks (reuse existing validators)
        try:
            validate_extension(original_filename)
        except InvalidFileException as exc:
            errors.append(str(exc))

        try:
            validate_file_size(file.size)
        except InvalidFileException as exc:
            errors.append(str(exc))

        try:
            validate_mime_type(mime_type)
        except InvalidFileException as exc:
            errors.append(str(exc))

        if errors:
            return {'is_valid': False, 'errors': errors}

        # 2. Structural check for PDFs (corrupted / password-protected)
        if mime_type == 'application/pdf':
            path = Path(file.temporary_file_path()) if hasattr(file, 'temporary_file_path') else None
            try:
                if path and path.exists():
                    if not pdf_processor.is_pdf(path):
                        errors.append('File is not a valid PDF (corrupted or not a PDF).')
                    else:
                        try:
                            pdf_processor.get_page_count(path)
                        except PDFProcessingException as exc:
                            errors.append(str(exc))
            except PDFProcessingException as exc:
                errors.append(str(exc))

        return {'is_valid': len(errors) == 0, 'errors': errors}

    def validate_business_rules(self, *, normalized: dict) -> dict:
        """
        Validate the normalized extraction against business rules.

        Checks required fields, item arithmetic, and tax/total
        consistency. Used after normalization to decide whether a
        document needs human review.

        Args:
            normalized: The normalized extraction dict (from
                ``NormalizationService``).

        Returns:
            A dict with ``is_valid`` and ``errors`` (list of message
            strings).
        """
        errors: list[str] = []

        # 1. Required fields must be present.
        for field in REQUIRED_FIELDS:
            value = normalized.get(field)
            if value is None or value == '':
                errors.append(f'Required field "{field}" is missing.')

        # 2. Item arithmetic: each line total should match qty * unit_price.
        for idx, item in enumerate(normalized.get('items') or []):
            qty = item.get('quantity')
            unit_price = item.get('unit_price')
            line_total = item.get('total')
            if qty is not None and unit_price is not None and line_total is not None:
                expected = round(qty * unit_price, 2)
                if abs(expected - line_total) > MONEY_TOLERANCE:
                    errors.append(
                        f'Item {idx + 1} total mismatch: '
                        f'{line_total} != {qty} * {unit_price} ({expected}).'
                    )

        # 3. Tax / total consistency: total should equal subtotal + tax.
        subtotal = normalized.get('subtotal')
        tax = normalized.get('tax')
        total = normalized.get('total')
        if subtotal is not None and tax is not None and total is not None:
            expected_total = round(subtotal + tax, 2)
            if abs(expected_total - total) > MONEY_TOLERANCE:
                errors.append(
                    f'Total mismatch: {total} != subtotal + tax '
                    f'({subtotal} + {tax} = {expected_total}).'
                )

        logger.info(
            'Business rule validation — valid=%s errors=%d',
            len(errors) == 0,
            len(errors),
        )
        return {'is_valid': len(errors) == 0, 'errors': errors}


validation_service = ValidationService()
