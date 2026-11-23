import math
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import fitz
from django.test import SimpleTestCase

from ocr import pdf_processor as module
from ocr.exceptions import PDFProcessingException, PDFTooLargeException


class PDFRenderingSafetyTests(SimpleTestCase):
    def test_mixed_page_sizes_are_bounded_even_with_high_dpi_override(self):
        # Guard before real rasterization so a regression cannot OOM the test runner.
        original_render = fitz.Page.get_pixmap

        def bounded_render(page, **kwargs):
            bounds = (page.rect * kwargs['matrix']).irect
            self.assertLessEqual(bounds.width, 4000)
            self.assertLessEqual(bounds.height, 4000)
            self.assertFalse(kwargs['alpha'])
            return original_render(page, **kwargs)

        with TemporaryDirectory() as directory:
            source = Path(directory) / 'oversized.pdf'
            with fitz.open() as document:
                for width, height in ((3000, 3000), (14400, 14400), (14400, 7200)):
                    document.new_page(width=width, height=height)
                document.save(source)
            with patch.object(module, 'TMP_ROOT', Path(directory)), patch.object(module, 'DPI', 300), patch.object(fitz.Page, 'get_pixmap', bounded_render):
                images = module.PDFProcessor().convert_to_images(source, 'rendered')
            self.assertEqual(len(images), 3)
            for image, expected in zip(images, ((4000, 4000), (4000, 4000), (4000, 2000))):
                pixmap = fitz.Pixmap(str(image))
                self.assertEqual((pixmap.width, pixmap.height), expected)
                del pixmap

    def test_normal_page_preserves_configured_dpi(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / 'normal.pdf'
            with fitz.open() as document:
                document.new_page(width=595, height=842)
                document.save(source)
            for dpi in (150, 200):
                with self.subTest(dpi=dpi), patch.object(module, 'TMP_ROOT', Path(directory)), patch.object(module, 'DPI', dpi):
                    images = module.PDFProcessor().convert_to_images(source, str(dpi))
                    pixmap = fitz.Pixmap(str(images[0]))
                    self.assertEqual((pixmap.width, pixmap.height), (math.ceil(595 * dpi / 72), math.ceil(842 * dpi / 72)))
                    del pixmap

    def test_invalid_dimensions_are_rejected_before_rendering(self):
        for dimensions in ((0, 100), (-1, 100), (float('nan'), 100), (100, float('inf'))):
            with self.subTest(dimensions=dimensions), TemporaryDirectory() as directory:
                page = Mock(rect=Mock(width=dimensions[0], height=dimensions[1]))
                document = Mock(page_count=1)
                document.load_page.return_value = page
                with patch.object(module, 'TMP_ROOT', Path(directory)), patch.object(module, 'get_fitz') as library:
                    library.return_value.open.return_value = document
                    with self.assertRaisesRegex(PDFProcessingException, 'dimensions'):
                        module.PDFProcessor().convert_to_images('invalid.pdf', 'invalid')
                page.get_pixmap.assert_not_called()
                document.close.assert_called_once()

    def test_page_count_limit_still_rejects_before_rendering(self):
        with TemporaryDirectory() as directory, patch.object(module, 'TMP_ROOT', Path(directory)), patch.object(module, 'get_fitz') as library:
            document = Mock(page_count=module.MAX_PAGES + 1)
            library.return_value.open.return_value = document
            with self.assertRaises(PDFTooLargeException):
                module.PDFProcessor().convert_to_images('too-many.pdf', 'limit')
            document.load_page.assert_not_called()
            document.close.assert_called_once()
