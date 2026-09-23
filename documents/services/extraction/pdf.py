"""PDF text extraction: pymupdf's embedded text layer first (fast, free,
works for any PDF generated from text), OCR.space (extraction/ocr.py) as a
fallback for a PDF that turns out to be scanned images with no text layer
to read.
"""

import logging
import os

import pymupdf
from django.core.files.storage import default_storage

from .ocr import ocr_pdf

logger = logging.getLogger(__name__)

# Below this many characters per page on average, a PDF is treated as
# scanned rather than merely short — pymupdf returns only whitespace/near-
# nothing for a genuine scan, while even a sparse real text page (a title
# slide, a mostly-blank form) clears this easily.
MIN_CHARS_PER_PAGE = 20


def extract_text_from_pdf(file_path: str) -> str:
    with default_storage.open(file_path, "rb") as file:
        pdf_bytes = file.read()

    pdf = pymupdf.open(stream=pdf_bytes, filetype="pdf")
    page_count = len(pdf)
    logger.info("Extracting text from %s (%d pages)", file_path, page_count)

    text = "\n".join(page.get_text() for page in pdf)
    pdf.close()

    if page_count and len(text.strip()) < MIN_CHARS_PER_PAGE * page_count:
        logger.info(
            "%s looks scanned (%d chars over %d pages) — falling back to OCR",
            file_path,
            len(text.strip()),
            page_count,
        )
        return ocr_pdf(pdf_bytes, filename=os.path.basename(file_path))

    return text
