"""
IDP engine service layer for the OCR application.

Each module below is isolated and single-responsibility. The
``pipeline_service`` orchestrates them in the correct order. Views stay
thin and delegate to these services.
"""

from ocr.services.ocr_service import OCRService, ocr_service

__all__ = ['OCRService', 'ocr_service']
