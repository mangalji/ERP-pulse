import tempfile
from pathlib import Path

import cv2
import easyocr
import fitz  # PyMuPDF
import numpy as np

from django.http import HttpResponse
from rest_framework import status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# Load EasyOCR once when Django imports this module.
# CPU is intentional for this local test.
reader = easyocr.Reader(["en"], gpu=False)


def preprocess_image(image):
    """
    Basic OpenCV preprocessing before OCR.
    """

    if image is None:
        raise ValueError("Unable to read image.")

    # BGR -> grayscale
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image

    # Upscale smaller documents
    height, width = gray.shape[:2]

    if width < 1500:
        scale = 1500 / width
        gray = cv2.resize(
            gray,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )

    # Light denoising
    gray = cv2.GaussianBlur(gray, (3, 3), 0)

    # Improve local contrast
    clahe = cv2.createCLAHE(
        clipLimit=2.0,
        tileGridSize=(8, 8),
    )

    gray = clahe.apply(gray)

    return gray


def extract_text_from_image(image):
    """
    OpenCV preprocessing + EasyOCR.
    Returns plain text only.
    """

    processed = preprocess_image(image)

    results = reader.readtext(
        processed,
        detail=0,
        paragraph=True,
    )

    return "\n".join(
        text.strip()
        for text in results
        if text and text.strip()
    )


def extract_text_from_pdf(pdf_path):
    """
    Render every PDF page to an image and OCR every page.
    """

    document = fitz.open(pdf_path)
    all_pages = []

    try:
        for page in document:

            pixmap = page.get_pixmap(
                dpi=300,
                alpha=False,
            )

            image = np.frombuffer(
                pixmap.samples,
                dtype=np.uint8,
            )

            image = image.reshape(
                pixmap.height,
                pixmap.width,
                pixmap.n,
            )

            # PyMuPDF gives RGB; OpenCV uses BGR.
            if pixmap.n == 3:
                image = cv2.cvtColor(
                    image,
                    cv2.COLOR_RGB2BGR,
                )

            page_text = extract_text_from_image(image)

            if page_text:
                all_pages.append(page_text)

    finally:
        document.close()

    return "\n\n".join(all_pages).strip()


class OCRTestExtractView(APIView):
    """
    Completely isolated OCR test.

    PDF/Image
        -> OpenCV
        -> EasyOCR
        -> plain text

    Does NOT use:
        Invoice module
        InvoiceService
        Gemini
        Celery
        Redis
        NetSuite
    """

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        uploaded_file = request.FILES.get("file")

        if not uploaded_file:
            return Response(
                {"detail": "No file uploaded."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if uploaded_file.size > MAX_FILE_SIZE:
            return Response(
                {"detail": "File size cannot exceed 10 MB."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        extension = Path(uploaded_file.name).suffix.lower()

        if extension not in ALLOWED_EXTENSIONS:
            return Response(
                {
                    "detail": (
                        "Only PDF, PNG, JPG and JPEG files "
                        "are supported."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        temp_path = None

        try:
            with tempfile.NamedTemporaryFile(
                suffix=extension,
                delete=False,
            ) as temp_file:

                for chunk in uploaded_file.chunks():
                    temp_file.write(chunk)

                temp_path = temp_file.name

            if extension == ".pdf":

                extracted_text = extract_text_from_pdf(
                    temp_path
                )

            else:

                image_data = np.fromfile(
                    temp_path,
                    dtype=np.uint8,
                )

                image = cv2.imdecode(
                    image_data,
                    cv2.IMREAD_COLOR,
                )

                extracted_text = extract_text_from_image(
                    image
                )

            return HttpResponse(
                extracted_text,
                content_type="text/plain; charset=utf-8",
            )

        except Exception as exc:

            return Response(
                {
                    "detail": f"OCR extraction failed: {str(exc)}"
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        finally:

            if temp_path:
                try:
                    Path(temp_path).unlink(missing_ok=True)
                except OSError:
                    pass