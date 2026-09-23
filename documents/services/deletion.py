from django.core.files.storage import default_storage

from documents.models import Document


def delete_documents(queryset):
    """Permanently deletes every document in an (already owner-scoped)
    queryset: each storage file, then all the rows (and, via
    DocumentChunk.document's on_delete=CASCADE, every chunk and pgvector
    embedding that came from them) in one query. Backs both
    DocumentDeleteAllView and DocumentBulkDeleteView — same guarantees,
    just a different queryset going in. Returns how many were deleted.
    """
    documents = list(queryset)

    for document in documents:
        if not document.file_path:
            continue
        try:
            default_storage.delete(document.file_path)
        except Exception:
            # One bad file (already gone, a transient storage error)
            # shouldn't stop the rest from being deleted — the DB rows are
            # still cleared below regardless.
            pass

    # One query for every row rather than N individual .delete() calls.
    Document.objects.filter(id__in=[d.id for d in documents]).delete()

    return len(documents)
