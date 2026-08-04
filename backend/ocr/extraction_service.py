"""
Extraction service for OCR invoice processing.

``OCRExtractionService`` orchestrates the full extraction pipeline:
1. Preprocess the image (via ImageProcessor)
2. Send to Gemini (via GeminiClient)
3. Validate the response schema (via schema.validate_extraction_result)
4. Calculate confidence scores
5. Return the structured result

No extracted data is saved to business tables yet — this phase only
returns the structured result.
"""

from __future__ import annotations
import time, uuid
from pathlib import Path

from django.conf import settings

from ocr.exceptions import (
    GeminiValidationException,
    OCRExtractionFailedException,
    OCRServiceException,
)
from ocr.gemini_client import GeminiClient
from ocr.image_processor import ImageProcessor, ImageQualityReport
from ocr.models import OCRUpload
from ocr.schema import validate_extraction_result
from ocr.utils import logger

#: Expected fields for confidence computation.
CONFIDENCE_FIELDS: list[str] = [
    'vendor', 'invoice_number', 'invoice_date',
    'currency', 'subtotal', 'tax', 'total', 'purchase_order',
]

class OCRExtractionService:
    """
    Orchestrates the full OCR extraction pipeline.

    This service is the single entry point for extracting structured
    data from an uploaded invoice file. It coordinates the image
    processor, Gemini client, and schema validator.

    Usage::

        service = OCRExtractionService()
        result = service.extract(upload, user)
    """

    def __init__(
        self,
        gemini_client: GeminiClient | None = None,
        image_processor: ImageProcessor | None = None,
    ) -> None:
        """
        Initialize the extraction service with dependency injection.

        Args:
            gemini_client: Gemini API client (auto-created if None).
            image_processor: Image processor (auto-created if None).
        """
        self.gemini_client = gemini_client or GeminiClient()
        self.image_processor = image_processor or ImageProcessor()

    def extract(self, upload: OCRUpload, user) -> dict:
        """
        Run the full extraction pipeline on an upload.

        Args:
            upload: The OCRUpload record to process.
            user: The authenticated user.

        Returns:
            A dictionary with the extraction result:
            {
                "extraction_id": "uuid",
                "upload_id": "uuid",
                "status": "COMPLETED",
                "data": { ... },
                "confidence": { ... },
                "image_quality": { ... },
                "processing_time_ms": 123.45
            }

        Raises:
            OCRServiceException: If the pipeline fails.
            GeminiValidationException: If schema validation fails.
        """
        extraction_id = uuid.uuid4()
        start = time.perf_counter()

        logger.info(
            'Extraction started — extraction_id=%s upload_id=%s user=%s',
            extraction_id, upload.id, user.id,
        )

        # Step 1: Generate image quality report
        image_path = Path(upload.file.path)
        quality_report = ImageQualityReport.from_image(image_path)

        # Step 2: Preprocess image
        processed_path = self.image_processor.preprocess(
            image_path, str(upload.id),
        )

        # Step 3: Extract with Gemini
        if not settings.OCR_ENABLE_GEMINI:
            raise OCRServiceException(
                'Gemini extraction is disabled. '
                'Set OCR_ENABLE_GEMINI=True to enable.'
            )

        extracted_data = self.gemini_client.extract(processed_path)

        # Step 4: Validate schema
        validated_data = validate_extraction_result(extracted_data)

        # Step 5: Calculate confidence
        confidence = self._calculate_confidence(validated_data)
        validated_data['confidence'] = confidence

        processing_time_ms = (time.perf_counter() - start) * 1000
        logger.info(
            'Extraction completed — extraction_id=%s upload_id=%s '
            'duration=%.2fms',
            extraction_id, upload.id, processing_time_ms,
        )

        return {
            'extraction_id': str(extraction_id),
            'upload_id': str(upload.id),
            'status': 'COMPLETED',
            'data': validated_data,
            'confidence': {
                'overall': confidence.get('overall', 0.0),
                'fields': confidence.get('fields', {}),
                'missing_fields': confidence.get('missing_fields', []),
                'low_confidence_fields': confidence.get('low_confidence_fields', []),
            },
            'image_quality': quality_report.as_dict(),
            'processing_time_ms': processing_time_ms,
        }

    @staticmethod
    def _calculate_confidence(data: dict) -> dict:
        """
        Calculate confidence scores for the extraction result.

        Confidence is computed as follows:
        - Fields present → 1.0
        - Fields with null values → 0.0
        - Overall confidence = mean of all field confidences

        Args:
            data: The validated extraction data.

        Returns:
            A dict with overall, fields, missing_fields, and
            low_confidence_fields.
        """
        fields: dict[str, float] = {}
        missing_fields: list[str] = []
        low_confidence_fields: list[str] = []

        for field in CONFIDENCE_FIELDS:
            value = data.get(field)
            if value is None or value == '' or value == []:
                fields[field] = 0.0
                missing_fields.append(field)
                low_confidence_fields.append(field)
            elif isinstance(value, (int, float)) and value == 0:
                # Zero is a valid value for subtotal/tax/total
                fields[field] = 0.8
            else:
                fields[field] = 1.0

        # Incorporate item-level confidence
        items = data.get('items', [])
        if items:
            item_confidence = min(1.0, len(items) * 0.2)
            fields['items'] = item_confidence
            if item_confidence < 0.5:
                low_confidence_fields.append('items')
        else:
            fields['items'] = 0.0
            missing_fields.append('items')
            low_confidence_fields.append('items')

        # Overall confidence = mean of all field confidences
        overall = sum(fields.values()) / len(fields) if fields else 0.0

        return {
            'overall': round(overall, 4),
            'fields': fields,
            'missing_fields': missing_fields,
            'low_confidence_fields': low_confidence_fields,
        }


#: Module-level singleton.
ocr_extraction_service = OCRExtractionService()