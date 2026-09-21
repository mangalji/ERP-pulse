"""
Image preprocessing pipeline for the OCR application.

``ImageProcessor`` wraps OpenCV and Pillow to enhance images before
they are sent to an AI vision model for OCR. The pipeline performs
orientation detection, deskewing, noise removal, contrast enhancement,
adaptive thresholding, sharpening, and resizing — all with
configurable parameters from Django settings.

``ImageQualityReport`` analyses an image and returns quality metrics
(brightness, contrast, blur, noise, rotation angle, processing time)
so the calling code can decide whether the image is suitable for OCR.

Usage::

    processor = ImageProcessor()
    processed_path = processor.preprocess(image_path, upload_id)
    report = ImageQualityReport.from_image(image_path)
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
from django.conf import settings
from PIL import Image

from ocr.exceptions import ImageProcessingException, InvalidImageException
from ocr.utils import logger

#: Root directory for processed image output.
PROCESSED_ROOT: Path = Path(settings.MEDIA_ROOT) / 'ocr' / 'processed'


class ImageProcessor:
    """
    Preprocess invoice images for OCR using OpenCV.

    The processor is stateless — each method call is independent, and
    the only state is the output directory path derived from the
    ``upload_id``. This makes the class safe to reuse across requests.

    The pipeline order is:
    1. Load image
    2. Detect orientation and auto-rotate
    3. Deskew
    4. Remove noise (conditional on noise score)
    5. Increase contrast
    6. Adaptive threshold (for grayscale images)
    7. Sharpen
    8. Resize for OCR
    9. Save and return path
    """

    def load_image(self, path: str | Path) -> np.ndarray:
        """
        Load an image from disk using OpenCV.

        Args:
            path: Path to the image file.

        Returns:
            Image as a NumPy array (OpenCV BGR format).

        Raises:
            InvalidImageException: If the file cannot be read, is
                empty, or has zero dimensions.
        """
        path = Path(path)
        if not path.exists():
            raise InvalidImageException(f'Image file not found: {path}')

        image = cv2.imread(str(path))
        if image is None:
            raise InvalidImageException(
                f'Failed to read image: {path}. '
                'The file may be corrupted or an unsupported format.'
            )
        if image.size == 0:
            raise InvalidImageException(f'Image is empty: {path}.')
        if image.shape[0] == 0 or image.shape[1] == 0:
            raise InvalidImageException(
                f'Image has zero dimensions: {path}.'
            )

        logger.info('Image loaded — path=%s shape=%s', path, image.shape)
        return image

    def save_image(self, image: np.ndarray, path: str | Path) -> Path:
        """
        Save an image to disk.

        The output directory is created if it does not exist.

        Args:
            image: Image as a NumPy array.
            path: Destination path.

        Returns:
            The absolute path of the saved file.

        Raises:
            ImageProcessingException: If the save fails.
        """
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        success = cv2.imwrite(str(path), image)
        if not success:
            raise ImageProcessingException(
                f'Failed to save image to {path}.'
            )
        logger.info('Image saved — path=%s', path)
        return path

    def convert_to_grayscale(self, image: np.ndarray) -> np.ndarray:
        """
        Convert a BGR image to grayscale.

        If the image is already single-channel (grayscale), it is
        returned unchanged.

        Args:
            image: Input image (BGR or grayscale).

        Returns:
            Grayscale image as a single-channel NumPy array.
        """
        if len(image.shape) == 2:
            return image
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        logger.debug('Image converted to grayscale.')
        return gray

    def remove_noise(self, image: np.ndarray) -> np.ndarray:
        """
        Apply Gaussian blur to reduce noise.

        The kernel size is read from ``OCR_DENOISE_KERNEL_SIZE`` in
        Django settings (default: 3).

        Args:
            image: Input image (grayscale or BGR).

        Returns:
            Denoised image.
        """
        kernel = settings.OCR_DENOISE_KERNEL_SIZE
        denoised = cv2.GaussianBlur(image, (kernel, kernel), 0)
        logger.debug('Noise removal applied — kernel=%d', kernel)
        return denoised

    def adaptive_threshold(self, image: np.ndarray) -> np.ndarray:
        """
        Apply adaptive thresholding to binarise a grayscale image.

        Uses ``cv2.ADAPTIVE_THRESH_GAUSSIAN_C``. The block size
        and constant are read from Django settings.

        Args:
            image: Grayscale input image.

        Returns:
            Binary image (inverted so text is white on black).

        Raises:
            ImageProcessingException: If the image is not grayscale.
        """
        if len(image.shape) != 2:
            raise ImageProcessingException(
                'Adaptive threshold requires a grayscale image. '
                'Call convert_to_grayscale() first.'
            )
        block = settings.OCR_THRESHOLD_BLOCK_SIZE
        c_val = settings.OCR_THRESHOLD_C
        threshold = cv2.adaptiveThreshold(
            image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY_INV, block, c_val,
        )
        # Invert back so text is black on white
        threshold = cv2.bitwise_not(threshold)
        logger.debug('Adaptive threshold applied — block=%d C=%d', block, c_val)
        return threshold

    def increase_contrast(self, image: np.ndarray) -> np.ndarray:
        """
        Increase image contrast using CLAHE (Contrast Limited Adaptive
        Histogram Equalization).

        For grayscale images, CLAHE is applied directly. For BGR
        images, CLAHE is applied to the L channel in LAB colour space.

        Args:
            image: Input image (grayscale or BGR).

        Returns:
            Contrast-enhanced image.
        """
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))

        if len(image.shape) == 2:
            result = clahe.apply(image)
        else:
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            l = clahe.apply(l)
            merged = cv2.merge([l, a, b])
            result = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

        logger.debug('Contrast enhancement applied.')
        return result

    def deskew(self, image: np.ndarray) -> np.ndarray:
        """
        Correct skew in a document image.

        The skew angle is detected via a projection profile method
        on a grayscale version of the image. The maximum correction
        angle and step size are read from Django settings.

        Args:
            image: Input image (grayscale or BGR).

        Returns:
            Deskewed image.
        """
        if len(image.shape) == 3:
            gray = self.convert_to_grayscale(image)
        else:
            gray = image

        angle = self._detect_skew_angle(gray)

        if abs(angle) < 0.5:
            logger.debug('No significant skew detected (angle=%.2f).', angle)
            return image

        h, w = gray.shape[:2]
        centre = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)
        cos = abs(matrix[0, 0])
        sin = abs(matrix[0, 1])
        new_w = int((h * sin) + (w * cos))
        new_h = int((h * cos) + (w * sin))
        matrix[0, 2] += (new_w / 2) - centre[0]
        matrix[1, 2] += (new_h / 2) - centre[1]

        result = cv2.warpAffine(
            image, matrix, (new_w, new_h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        logger.debug('Deskew applied — angle=%.2f', angle)
        return result

    def resize_for_ocr(self, image: np.ndarray) -> np.ndarray:
        """
        Resize an image to a target width suitable for OCR.

        The target width is read from ``OCR_TARGET_WIDTH`` in Django
        settings. Aspect ratio is preserved. Images smaller than the
        target are upscaled only if they are below
        ``OCR_MIN_IMAGE_WIDTH``.

        Args:
            image: Input image.

        Returns:
            Resized image.

        Raises:
            InvalidImageException: If the image is too small for OCR.
        """
        h, w = image.shape[:2]
        target_w = settings.OCR_TARGET_WIDTH
        min_w = settings.OCR_MIN_IMAGE_WIDTH

        if w < min_w:
            raise InvalidImageException(
                f'Image width {w}px is below the minimum '
                f'of {min_w}px required for OCR.'
            )

        if w == target_w:
            return image

        scale = target_w / w
        new_w = int(w * scale)
        new_h = int(h * scale)
        result = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
        logger.debug('Image resized — %dx%d → %dx%d', w, h, new_w, new_h)
        return result

    def sharpen(self, image: np.ndarray) -> np.ndarray:
        """
        Apply a sharpening kernel to enhance text edges.

        The kernel strength is read from ``OCR_SHARPEN_STRENGTH`` in
        Django settings (default: 0.5). A value of 0 means no
        sharpening; 1.0 is maximum.

        Args:
            image: Input image.

        Returns:
            Sharpened image.
        """
        strength = settings.OCR_SHARPEN_STRENGTH
        if strength <= 0:
            return image

        kernel = np.array([
            [0, -strength, 0],
            [-strength, 1 + 4 * strength, -strength],
            [0, -strength, 0],
        ], dtype=np.float32)

        result = cv2.filter2D(image, -1, kernel)
        logger.debug('Sharpening applied — strength=%.2f', strength)
        return result

    def detect_orientation(self, image: np.ndarray) -> float:
        """
        Detect the orientation of a document image in degrees.

        Uses OpenCV's ``minAreaRect`` to find the dominant text
        angle. Returns an angle in the range [-45, 45] where 0 means
        upright.

        Args:
            image: Input image (grayscale or BGR).

        Returns:
            Orientation angle in degrees. Positive = clockwise tilt.
        """
        if len(image.shape) == 3:
            gray = self.convert_to_grayscale(image)
        else:
            gray = image

        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(binary)

        if coords is None or len(coords) < 10:
            return 0.0

        # minAreaRect returns (center, (width, height), angle) in OpenCV 5
        _, _, angle = cv2.minAreaRect(coords)
        if angle < -45:
            angle = 90 + angle
        elif angle > 45:
            angle = angle - 90

        logger.debug('Orientation detected — angle=%.2f', angle)
        return angle

    def auto_rotate(self, image: np.ndarray) -> np.ndarray:
        """
        Automatically rotate an image to the upright orientation.

        Combines orientation detection with a 4-way test (0°, 90°,
        180°, 270°) to handle images that are 90° off (where
        ``detect_orientation`` would not correct).

        Args:
            image: Input image.

        Returns:
            Correctly oriented image.
        """
        if len(image.shape) == 3:
            gray = self.convert_to_grayscale(image)
        else:
            gray = image

        angles = [0, 90, 180, 270]
        best_angle = 0
        best_score = 0

        for angle in angles:
            if angle == 0:
                rotated = gray
            else:
                h, w = gray.shape[:2]
                centre = (w // 2, h // 2)
                matrix = cv2.getRotationMatrix2D(centre, angle, 1.0)
                rotated = cv2.warpAffine(
                    gray, matrix, (w, h),
                    borderMode=cv2.BORDER_REPLICATE,
                )

            edges = cv2.Sobel(rotated, cv2.CV_64F, 1, 0, ksize=3)
            score = np.sum(np.abs(edges))
            if score > best_score:
                best_score = score
                best_angle = angle

        fine_angle = self.detect_orientation(image)
        total_angle = best_angle + fine_angle

        if abs(total_angle) < 1.0:
            return image

        h, w = gray.shape[:2]
        centre = (w // 2, h // 2)
        matrix = cv2.getRotationMatrix2D(centre, total_angle, 1.0)
        rotated = cv2.warpAffine(
            image, matrix, (w, h),
            flags=cv2.INTER_CUBIC,
            borderMode=cv2.BORDER_REPLICATE,
        )
        logger.debug('Auto-rotate applied — total_angle=%.2f', total_angle)
        return rotated

    def preprocess(self, image_path: str | Path, upload_id: str) -> Path:
        """
        Run the full preprocessing pipeline on an image.

        Pipeline steps:
        1. Load
        2. Orientation detection -> auto-rotate
        3. Deskew
        4. Noise removal (conditional)
        5. Contrast enhancement
        6. Adaptive thresholding
        7. Sharpening
        8. Resize for OCR
        9. Save to ``MEDIA_ROOT/ocr/processed/<upload_id>/``

        Args:
            image_path: Path to the input image.
            upload_id: UUID of the ``OCRUpload`` record.

        Returns:
            Path to the processed image.

        Raises:
            InvalidImageException: If the input image is invalid.
            ImageProcessingException: If any pipeline step fails.
        """
        start = time.perf_counter()
        image_path = Path(image_path)

        logger.info(
            'Preprocessing started — path=%s upload_id=%s',
            image_path, upload_id,
        )

        image = self.load_image(image_path)
        image = self.auto_rotate(image)
        image = self.deskew(image)

        gray = self.convert_to_grayscale(image) if len(image.shape) == 3 else image
        noise_score = self._compute_noise_score(gray)
        if noise_score > settings.OCR_MAX_NOISE_SCORE:
            image = self.remove_noise(image)
            logger.info('Noise removal applied — noise_score=%.2f', noise_score)
        else:
            logger.info(
                'Noise removal skipped — noise_score=%.2f below threshold=%.2f',
                noise_score, settings.OCR_MAX_NOISE_SCORE,
            )

        image = self.increase_contrast(image)
        gray = self.convert_to_grayscale(image) if len(image.shape) == 3 else image
        image = self.adaptive_threshold(gray)
        image = self.sharpen(image)
        image = self.resize_for_ocr(image)

        output_dir = self._get_output_dir(upload_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f'{image_path.stem}_processed.png'
        self.save_image(image, output_path)

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            'Preprocessing completed — upload_id=%s input=%s output=%s duration=%.2fms',
            upload_id, image_path, output_path, duration_ms,
        )
        return output_path

    @staticmethod
    def _detect_skew_angle(gray: np.ndarray) -> float:
        """
        Detect the skew angle of a grayscale document image.

        Uses a projection profile method.

        Args:
            gray: Grayscale input image.

        Returns:
            Skew angle in degrees. Positive = clockwise tilt.
        """
        _, binary = cv2.threshold(gray, 128, 255, cv2.THRESH_BINARY_INV)
        coords = cv2.findNonZero(binary)

        if coords is None or len(coords) < 10:
            return 0.0

        max_angle = settings.OCR_MAX_SKEW_ANGLE
        angle_step = settings.OCR_SKEW_ANGLE_STEP
        best_angle = 0.0
        best_variance = 0.0

        for angle in np.arange(-max_angle, max_angle + angle_step, angle_step):
            matrix = cv2.getRotationMatrix2D((0, 0), angle, 1.0)
            rotated = cv2.warpAffine(
                binary, matrix, (binary.shape[1], binary.shape[0]),
                borderMode=cv2.BORDER_REPLICATE,
            )
            projection = np.sum(rotated, axis=1)
            variance = np.var(projection)
            if variance > best_variance:
                best_variance = variance
                best_angle = angle

        return best_angle

    @staticmethod
    def _compute_noise_score(gray: np.ndarray) -> float:
        """
        Compute a noise score for a grayscale image.

        Args:
            gray: Grayscale input image.

        Returns:
            Noise score (float).
        """
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        return float(np.mean(np.abs(laplacian)))

    @staticmethod
    def _get_output_dir(upload_id: str) -> Path:
        """Return the output directory for processed images."""
        return PROCESSED_ROOT / str(upload_id)


class ImageQualityReport:
    """
    Quality metrics for an image, computed at construction time.

    Attributes:
        path:            Path to the image file.
        width:           Image width in pixels.
        height:          Image height in pixels.
        dpi:             DPI if available, else ``None``.
        brightness:      Mean brightness (0-255).
        contrast:        Standard deviation of pixel values.
        blur_score:      Variance of Laplacian (lower = blurrier).
        noise_score:     Mean absolute Laplacian value.
        rotation_angle:  Detected rotation angle in degrees.
        processing_time_ms: Time taken to compute the report.
    """

    def __init__(self, image_path: str | Path) -> None:
        start = time.perf_counter()
        path = Path(image_path)

        pil_img = Image.open(path)
        self.path = path
        self.width = pil_img.width
        self.height = pil_img.height
        self.dpi = self._get_dpi(pil_img)
        pil_img.close()

        cv_img = cv2.imread(str(path))
        gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY) if len(cv_img.shape) == 3 else cv_img

        self.brightness = float(np.mean(gray))
        self.contrast = float(np.std(gray))
        self.blur_score = float(np.var(cv2.Laplacian(gray, cv2.CV_64F)))
        self.noise_score = float(np.mean(np.abs(cv2.Laplacian(gray, cv2.CV_64F))))

        processor = ImageProcessor()
        self.rotation_angle = processor.detect_orientation(cv_img)
        self.processing_time_ms = (time.perf_counter() - start) * 1000

    @classmethod
    def from_image(cls, image_path: str | Path) -> ImageQualityReport:
        """Create an ``ImageQualityReport`` for the given image."""
        return cls(image_path)

    @staticmethod
    def _get_dpi(image: Image.Image) -> int | None:
        """Extract DPI from a Pillow image."""
        dpi = image.info.get('dpi')
        if dpi and len(dpi) >= 1:
            return int(dpi[0])
        return None

    def as_dict(self) -> dict:
        """Return the report as a dictionary."""
        return {
            'path': str(self.path),
            'width': self.width,
            'height': self.height,
            'dpi': self.dpi,
            'brightness': round(self.brightness, 2),
            'contrast': round(self.contrast, 2),
            'blur_score': round(self.blur_score, 2),
            'noise_score': round(self.noise_score, 2),
            'rotation_angle': round(self.rotation_angle, 2),
            'processing_time_ms': round(self.processing_time_ms, 2),
        }


#: Module-level singleton.
image_processor = ImageProcessor()