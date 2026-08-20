"""
OCR module configuration for AGSuite ERP.

All OCR-related configurable values live here so no magic numbers
appear inside the OCR codebase. Values can be overridden via
environment variables for environment-specific tuning.
"""

from decouple import config

# ------------------------------------------------------------------
# PDF Processing
# ------------------------------------------------------------------

#: Maximum number of pages a PDF may have to be processed.
OCR_MAX_PAGES: int = config('OCR_MAX_PAGES', default=100, cast=int)

#: DPI (dots per inch) for PDF-to-image conversion.
OCR_PDF_DPI: int = config('OCR_PDF_DPI', default=300, cast=int)

# ------------------------------------------------------------------
# Image Processing
# ------------------------------------------------------------------

#: Target width (in pixels) for resized images sent to OCR.

OCR_TARGET_WIDTH: int = config('OCR_TARGET_WIDTH', default=2048, cast=int)

#: Minimum acceptable image width. Images below this are rejected.
OCR_MIN_IMAGE_WIDTH: int = config('OCR_MIN_IMAGE_WIDTH', default=256, cast=int)

#: Maximum image dimension (width or height) before rejection.
OCR_MAX_IMAGE_SIZE: int = config('OCR_MAX_IMAGE_SIZE', default=10000, cast=int)

#: Blur threshold — images with a blur score below this are
#: considered too blurry for reliable OCR.
OCR_BLUR_THRESHOLD: float = config('OCR_BLUR_THRESHOLD', default=100.0, cast=float)

#: Minimum acceptable contrast score. Images below this are
#: considered too low-contrast for reliable OCR.
OCR_MIN_CONTRAST: float = config('OCR_MIN_CONTRAST', default=20.0, cast=float)

#: Maximum noise score before the noise-removal stage is skipped

OCR_MAX_NOISE_SCORE: float = config('OCR_MAX_NOISE_SCORE', default=50.0, cast=float)

#: Gaussian blur kernel size for noise removal (must be odd, >= 3).
OCR_DENOISE_KERNEL_SIZE: int = config('OCR_DENOISE_KERNEL_SIZE', default=3, cast=int)

#: Adaptive threshold block size (must be odd, >= 3).
OCR_THRESHOLD_BLOCK_SIZE: int = config('OCR_THRESHOLD_BLOCK_SIZE', default=15, cast=int)

#: Adaptive threshold constant subtracted from the mean.
OCR_THRESHOLD_C: int = config('OCR_THRESHOLD_C', default=10, cast=int)

#: Maximum angle (in degrees) for deskew correction.
OCR_MAX_SKEW_ANGLE: float = config('OCR_MAX_SKEW_ANGLE', default=45.0, cast=float)

#: Angle step (in degrees) for skew detection search.
OCR_SKEW_ANGLE_STEP: float = config('OCR_SKEW_ANGLE_STEP', default=1.0, cast=float)

#: Sharpening kernel strength.
OCR_SHARPEN_STRENGTH: float = config('OCR_SHARPEN_STRENGTH', default=0.5, cast=float)

# ------------------------------------------------------------------
# Gemini API
# ------------------------------------------------------------------

#: Gemini model name for OCR extraction.
OCR_GEMINI_MODEL: str = config('OCR_GEMINI_MODEL', default='gemini-2.5-flash')

#: Request timeout in seconds for Gemini API calls.
OCR_TIMEOUT: int = config('OCR_TIMEOUT', default=180, cast=int)

#: Maximum number of retry attempts on failure.
OCR_MAX_RETRIES: int = config('OCR_MAX_RETRIES', default=3, cast=int)

#: Base delay in seconds for exponential backoff.
OCR_RETRY_DELAY: float = config('OCR_RETRY_DELAY', default=1.0, cast=float)

#: Maximum image size in MB allowed for Gemini processing.
OCR_MAX_IMAGE_SIZE_MB: int = config('OCR_MAX_IMAGE_SIZE_MB', default=20, cast=int)

#: Confidence threshold below which extraction is considered unreliable.
OCR_CONFIDENCE_THRESHOLD: float = config('OCR_CONFIDENCE_THRESHOLD', default=0.5, cast=float)

#: Master switch to enable/disable Gemini extraction.
OCR_ENABLE_GEMINI: bool = config('OCR_ENABLE_GEMINI', default=False, cast=bool)

OCR_MAX_UPLOAD_SIZE_MB: int = config(
    'OCR_MAX_UPLOAD_SIZE_MB',
    default=10,
    cast=int,
)

OCR_MAX_ZIP_FILES: int = config(
    'OCR_MAX_ZIP_FILES',
    default=20,
    cast=int,
)

OCR_MAX_ZIP_SIZE_MB: int = config(
    'OCR_MAX_ZIP_SIZE_MB',
    default=50,
    cast=int,
)

OCR_MAX_ZIP_UNCOMPRESSED_MB: int = config(
    'OCR_MAX_ZIP_UNCOMPRESSED_MB',
    default=100,
    cast=int,
)

# Maximum number of Gemini calls that may be active across all workers.
OCR_GEMINI_MAX_CONCURRENCY: int = config(
    'OCR_GEMINI_MAX_CONCURRENCY',
    default=2,
    cast=int,
)

# Application-side rolling requests-per-minute ceiling.
# Keep this BELOW your actual Gemini project quota.
OCR_GEMINI_TARGET_RPM: int = config(
    'OCR_GEMINI_TARGET_RPM',
    default=8,
    cast=int,
)

# Lease for the distributed concurrency slot.
OCR_GEMINI_CONCURRENCY_LEASE_SECONDS: int = config(
    'OCR_GEMINI_CONCURRENCY_LEASE_SECONDS',
    default=180,
    cast=int,
)
