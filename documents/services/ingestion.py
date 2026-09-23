import logging

from django.core.files.storage import default_storage

from documents.services.chunking import save_chunks, split_text
from documents.services.embeddings import embed_document
from documents.services.extraction.pdf import extract_text_from_pdf

logger = logging.getLogger(__name__)


def extract_text(document):
    """Best-effort text extraction based on what was actually uploaded.
    Returns None for a type we don't know how to read yet, rather than
    raising — an unsupported file type isn't a failed upload, just one
    that ask/ can't answer questions about."""
    if document.file_type == "application/pdf":
        return extract_text_from_pdf(document.file_path)

    if document.file_type.startswith("text/"):
        with default_storage.open(document.file_path, "rb") as file:
            return file.read().decode("utf-8", errors="ignore")

    return None


def run_ingestion(document):
    """Extract -> chunk -> embed a document, so it becomes answerable
    through documents/ask/. This is the actual work only — it raises on
    failure rather than catching anything, and never touches `status`.

    Status and retry decisions live one level up, in
    documents.tasks.ingest_document_task: they're genuinely different
    concerns (this function doesn't know how many retries are left or
    whether it's running for the 1st or 3rd time), and bundling them here
    made this untestable in isolation from Celery. A document whose
    content we simply can't read yet (extract_text returns None) is not a
    failure — it's a no-op, since there's nothing to chunk or embed.

    Chunking only happens once, ever, per document — guarded by whether
    any DocumentChunk rows already exist. Without this, a Celery retry
    (which re-runs this whole function from scratch) would re-extract,
    re-split and call save_chunks() again; save_chunks() has no way to
    know chunks already exist and would bulk_create a second full set of
    rows for the same content, embedding-and-billing the ones that
    already succeeded a second time and permanently duplicating every
    chunk in retrieval (the same passage answering ask/ twice). Skipping
    straight to embed_document() on a retry is also just the correct
    behavior: it already re-embeds only chunks with embedding=None, so a
    retry does exactly "redo what's left", not "redo everything."
    """
    if document.chunks.exists():
        embed_document(document)
        return

    text = extract_text(document)
    if text and text.strip():
        chunks = split_text(text)
        save_chunks(document, chunks)
        embed_document(document)
