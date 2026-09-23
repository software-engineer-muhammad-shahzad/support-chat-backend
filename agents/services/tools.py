from documents.models import Document
from rag.services.pipeline import get_relevant_chunks

from .web import FetchError, fetch_webpage_text


def fetch_webpage(url: str) -> str:
    """Fetch a public webpage and return its visible text content.

    Use this only when the user gives you a URL, or explicitly asks you
    to look something up on an external website — not for questions
    about the user's own uploaded documents.

    Args:
        url: The full http:// or https:// address of the page to read.
    """
    try:
        return fetch_webpage_text(url)
    except FetchError as exc:
        return f"Could not fetch that page: {exc}"


def make_get_documents_tool(owner):
    """Builds the get_documents tool for one request, with `owner` bound
    via closure — same reasoning as make_search_documents_tool below: the
    model never supplies (or sees) whose documents these are."""

    def get_documents() -> list[dict]:
        """List the authenticated user's uploaded documents, with each one's name and processing status.

        Use this for questions about which documents exist, how many
        there are, or whether one has finished processing yet (status is
        one of "processing", "completed", or "failed"). Not for questions
        about what a document actually says — use search_documents for
        that instead.
        """
        documents = Document.objects.filter(owner=owner).order_by("-created_at")
        return [
            {
                "id": document.id,
                "name": document.name,
                "status": document.status,
                "uploaded_at": document.created_at.isoformat(),
            }
            for document in documents
        ]

    return get_documents


def make_search_documents_tool(owner, documents=None):
    """Builds the search_documents tool for one request, with `owner` (and
    optional `documents` scope) bound via closure. Gemini only ever
    supplies `query` itself — owner/documents come from the authenticated
    request, never from the model, so there's no way for a prompt to make
    this search anyone else's files.

    Returned as a plain function (not a manually-declared
    types.FunctionDeclaration) because the google-genai SDK infers the
    tool's schema straight from this signature and docstring, and calls it
    directly as part of automatic function calling — see agent.py.
    """

    def search_documents(query: str) -> list[dict]:
        """Search the authenticated user's uploaded documents for information relevant to their question.

        Args:
            query: The question to search for in the user's documents.
        """
        chunks = get_relevant_chunks(query, owner=owner, documents=documents)
        return [
            {"document_name": chunk.document.name, "content": chunk.content}
            for chunk in chunks
        ]

    return search_documents
