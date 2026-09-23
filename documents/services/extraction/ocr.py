"""OCR.space integration — text extraction for scanned PDFs (a page image
with no embedded text layer for pymupdf to read directly). Used as a
fallback from extraction/pdf.py when native extraction comes back empty.
"""

import logging

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

OCR_SPACE_URL = "https://api.ocr.space/parse/image"
# Generous — a multi-page scan can genuinely take a while on OCR.space's
# free tier, and there's no partial progress to show while it runs anyway.
OCR_REQUEST_TIMEOUT_SECONDS = 120


class OcrError(Exception):
    """OCR.space itself reported a failure — bad key, unsupported file, or
    over the plan's page/size limit (free keys: 1MB per file, first 3 pages
    of a PDF). Distinct from a network/HTTP-level failure, which
    `requests` raises on its own via raise_for_status()."""


def ocr_pdf(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """Runs OCR.space's engine over a scanned PDF's raw bytes and returns
    the extracted text, one page's text per line in page order."""
    response = requests.post(
        OCR_SPACE_URL,
        data={
            "apikey": settings.OCR_SPACE_API_KEY,
            "language": "eng",
            "filetype": "PDF",
            "isOverlayRequired": False,
            # Engine 2 reads a wider range of scan quality/layouts than the
            # default engine 1 — worth it for a feature whose whole point
            # is handling messier input than a normal text-layer PDF.
            "OCREngine": 2,
        },
        files={"file": (filename, pdf_bytes, "application/pdf")},
        timeout=OCR_REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    result = response.json()

    if result.get("IsErroredOnProcessing"):
        message = (
            result.get("ErrorMessage")
            or result.get("ErrorDetails")
            or "Unknown OCR.space error"
        )
        if isinstance(message, list):
            message = "; ".join(message)
        raise OcrError(message)

    pages = [parsed.get("ParsedText", "") for parsed in result.get("ParsedResults", [])]
    return "\n".join(pages)
