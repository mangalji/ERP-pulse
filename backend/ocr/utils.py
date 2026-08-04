"""
Shared utilities for the OCR application.

Centralises the module logger so every file in the ``ocr`` package can
import a single, consistently-named logger instead of each file calling
``logging.getLogger(__name__)`` with a different name.

Usage::

    from ocr.utils import logger

    logger.info('Processing upload %s', upload_id)
"""

import logging

#: Module-level logger for the entire OCR application.
#:
#: Named ``ocr`` (not ``ocr.utils``) so log records are easy to filter
#: regardless of which sub-module emitted them.
logger: logging.Logger = logging.getLogger('ocr')