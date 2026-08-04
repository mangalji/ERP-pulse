"""
PDF processing infrastructure for the OCR application.

``PDFProcessor`` wraps PyMuPDF (``fitz``) to convert PDF documents into
PNG images — one per page — at 300 DPI in RGB. The images are written
to a temporary directory under ``MEDIA_ROOT/ocr/tmp/<upload_id>/`` and
returned as a list of ``pathlib.Path`` objects.

No OCR extraction happens here — this module only handles the
PDF-to-image conversion that must occur before an AI vision model can
read the invoice content.

Usage::

    processor = PDFProcessor()
    if processor.is_pdf(file_path):
        page_count = processor.get_page_count(file_path)
        images = processor.convert_to_images(file_path, upload_id)
        # ... feed images to AI model ...
        processor.cleanup(upload_id)
"""

from __future__ import annotations
import shutil, time
from pathlib import Path
import fitz
from django.conf import settings
from ocr.exceptions import PDFProcessingException, PDFTooLargeException
from ocr.utils import logger

#: Maximum number of pages a PDF may have to be processed.
MAX_PAGES: int = settings.OCR_MAX_PAGES

#: DPI (dots per inch) for PDF-to-image conversion.
#: Read from Django settings (default: 300).
#: 300 is the industry standard for OCR — lower values lose detail,
#: higher values increase memory and processing time without
#: meaningful accuracy gains for invoice text.
DPI: int = settings.OCR_PDF_DPI

#: Root directory for temporary PDF conversion output.
TMP_ROOT: Path = Path(settings.MEDIA_ROOT) / 'ocr' / 'tmp'

class PDFProcessor:
    """
    Convert PDF files to PNG images using PyMuPDF.

    The processor is stateless — each method call is independent, and
    the only state is the temporary directory path derived from the
    ``upload_id``. This makes the class safe to reuse across requests
    (the module-level singleton at the bottom mirrors the pattern used
    by ``OCRService``).
    """
    def is_pdf(self,file_path: str|Path)-> bool:
        """
        Check whether the file at ``file_path`` is a valid, openable PDF.

        Args:
            file_path: Path to the file to check.

        Returns:
            ``True`` if the file can be opened as a PDF, ``False``
            otherwise. No exception is raised — callers use this for
            a quick pre-check before calling ``get_page_count`` or
            ``convert_to_images``.
        """
        try:
            doc = fitz.open(str(file_path))
            is_valid = doc.is_pdf
            doc.close()
            return is_valid
        except Exception:
            return False

    def get_page_count(self,file_path: str | Path) -> int: 
        """
        Return the number of pages in the PDF at ``file_path``.

        Args:
            file_path: Path to the PDF file.

        Returns:
            The page count.

        Raises:
            PDFProcessingException: If the file cannot be opened or is
                not a valid PDF.
        """
        try:
            doc = fitz.open(str(file_path))
            count = doc.page_count
            doc.close()
            return count
        except Exception as exc:
            raise PDFProcessingException(
                f'Failed to read page count from {file_path}: {exc}'
            ) from exc

    def convert_to_images(
        self,
        file_path: str | Path,
        upload_id: str,
    ) -> list[Path]:
        """
        Convert every page of the PDF at ``file_path`` to a PNG image.

        Images are written to ``MEDIA_ROOT/ocr/tmp/<upload_id>/`` with
        filenames ``page_001.png``, ``page_002.png``, etc.

        Args:
            file_path: Path to the PDF file.
            upload_id: UUID of the ``OCRUpload`` record — used to
                isolate this conversion's temporary files from other
                uploads.

        Returns:
            A list of ``pathlib.Path`` objects, one per page, in page
            order.

        Raises:
            PDFProcessingException: If the PDF cannot be opened or
                rendered.
            PDFTooLargeException: If the PDF exceeds ``MAX_PAGES``.
        """
        start = time.perf_counter()
        output_dir = self._get_output_dir(upload_id)
        output_dir.mkdir(parents=True, exist_ok=True)

        try:
            doc = fitz.open(str(file_path))
        except Exception as exc:
            raise PDFProcessingException(
                f'Failed to open PDF {file_path}: {exc}'
            ) from exc

        page_count = doc.page_count

        if page_count > MAX_PAGES:
            doc.close()
            raise PDFTooLargeException(
                f'PDF has {page_count} pages, exceeding the maximum '
                f'of {MAX_PAGES} pages.'
            )

        images: list[Path] = []
        zoom = DPI / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        try:
            for page_num in range(page_count):
                page = doc.load_page(page_num)
                pix = page.get_pixmap(matrix=matrix, colorspace=fitz.csRGB)
                image_path = output_dir / f'page_{page_num + 1:03d}.png'
                pix.save(str(image_path))
                images.append(image_path)
        except Exception as exc:
            raise PDFProcessingException(
                f'Failed to render page {page_num + 1} of {file_path}: {exc}'
            ) from exc
        finally:
            doc.close()

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            'PDF conversion completed — upload_id=%s pages=%d '
            'duration=%.2fms',
            upload_id,
            page_count,
            duration_ms,
        )

        return images

    def cleanup(self, upload_id: str) -> None:
        """
        Delete the temporary directory and all images for ``upload_id``.

        Safe to call even if the directory does not exist — the method
        swallows ``FileNotFoundError`` so callers don't need to guard
        against double-cleanup.

        Args:
            upload_id: UUID of the ``OCRUpload`` whose temporary files
                should be removed.
        """
        output_dir = self._get_output_dir(upload_id)
        try:
            shutil.rmtree(output_dir)
            logger.info(
                'PDF cleanup completed — upload_id=%s dir=%s',
                upload_id,
                output_dir,
            )
        except FileNotFoundError:
            pass
        except Exception:
            logger.exception(
                'Failed to clean up temporary directory %s for upload %s.',
                output_dir,
                upload_id,
            )

    @staticmethod
    def _get_output_dir(upload_id: str) -> Path:
        """
        Return the temporary output directory for ``upload_id``.

        The directory is ``MEDIA_ROOT/ocr/tmp/<upload_id>/``. It is
        not created here — callers (``convert_to_images``) create it
        via ``mkdir(parents=True, exist_ok=True)``.

        Args:
            upload_id: UUID of the ``OCRUpload`` record.

        Returns:
            The ``Path`` to the temporary directory (may not exist yet).
        """
        return TMP_ROOT / str(upload_id)


#: Module-level singleton, mirroring the pattern in ocr/services.py.
pdf_processor = PDFProcessor()