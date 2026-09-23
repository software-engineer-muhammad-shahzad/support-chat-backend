from django.conf import settings
from google import genai
from google.genai import types

from .tools import fetch_webpage, make_get_documents_tool, make_search_documents_tool

client = genai.Client(api_key=settings.GEMINI_API_KEY)

MODEL = "gemini-3.5-flash-lite"

SYSTEM_INSTRUCTION = (
    "You are a support assistant with three tools: search_documents (looks "
    "up relevant content inside the user's uploaded documents), "
    "get_documents (lists the documents themselves — names and processing "
    "status, not their content), and fetch_webpage (reads the text of a "
    "public URL). Use get_documents for questions about which documents "
    "exist, how many there are, or whether one has finished processing; "
    "use search_documents for anything about what a document actually "
    "says; use fetch_webpage only when the user gives you a URL or "
    "explicitly asks you to check an external website. For everything "
    "else, use one of the document tools rather than answering from your "
    "own knowledge — if their results don't contain the answer, respond "
    'with exactly: "I couldn\'t find that information in the uploaded '
    'documents." Never fabricate information; only use what the tools '
    "actually return."
)


def run_agent(question, owner, documents=None):
    """Answers one question by giving Gemini this request's tools —
    search_documents and get_documents (agents.services.tools), both bound
    to `owner`/`documents` via closure, plus the stateless fetch_webpage —
    and letting it decide which, if any, to call. The google-genai SDK's
    automatic function calling (Chat.send_message) handles the full round
    trip — call the tool, feed its result back to the model, synthesize a
    final answer — internally; we don't drive that loop by hand.

    This is the entry point for documents/ask/-equivalent questions:
    retrieval + reranking (rag.services.pipeline.get_relevant_chunks)
    happen exactly as before, just from inside search_documents, on the
    model's own decision, rather than unconditionally on every question.
    """
    tools = [
        make_search_documents_tool(owner, documents),
        make_get_documents_tool(owner),
        fetch_webpage,
    ]

    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            tools=tools,
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )
    response = chat.send_message(question)

    return {"answer": response.text}
