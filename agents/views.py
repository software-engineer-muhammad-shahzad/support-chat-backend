from google.genai import errors as genai_errors
from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from documents.models import Document

from .services.agent import run_agent


class AgentAskView(generics.GenericAPIView):
    """POST {question, document_ids?} — answers a question by handing it to
    the AI agent (services/agent.py::run_agent), which decides whether to
    search the caller's uploaded documents (via the search_documents tool,
    rag/services/pipeline.py under the hood) and grounds its answer in
    whatever it finds. Always owner-scoped: omitting document_ids lets the
    agent search every one of the caller's own documents, never anyone
    else's; passing specific ids narrows the tool to just those (404s if
    any don't exist or aren't owned by the caller, rather than silently
    searching a smaller set than requested).

    This replaces documents/ask/ (formerly documents.views.AskQuestionView,
    which called the RAG pipeline directly) — the agent now sits in front
    of the RAG pipeline instead of it running unconditionally on every
    question.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        question = request.data.get("question")
        document_ids = request.data.get("document_ids") or []

        if not question:
            return Response(
                {"question": "This field is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        documents = None

        if document_ids:
            documents = list(
                Document.objects.filter(id__in=document_ids, owner=request.user)
            )
            # Catches both a bad id and someone else's document — same 404
            # either way, rather than silently searching fewer documents
            # than the caller actually asked for.
            if len(documents) != len(set(document_ids)):
                return Response(
                    {"detail": "One or more documents were not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        try:
            result = run_agent(
                question=question,
                owner=request.user,
                documents=documents,
            )
        except genai_errors.ClientError as exc:
            if exc.code == 429:
                # Gemini's free tier caps generate_content at 20/day — hit
                # this for real during development. Without this, it was an
                # unhandled 500 with a raw traceback; the frontend's error
                # parser (lib/api/types.ts::parseErrorBody) already reads
                # {"detail": ...} as the display message, so this alone is
                # enough for a real "try again later" toast, no frontend
                # change needed.
                return Response(
                    {
                        "detail": "The AI service's usage quota has been reached. Please try again later.",
                    },
                    status=status.HTTP_429_TOO_MANY_REQUESTS,
                )
            # Any other client error (bad request to the API, auth issue,
            # etc.) isn't something the caller can do anything about either
            # — surface it the same way rather than a generic 500.
            return Response(
                {"detail": "The AI service couldn't process that request."},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "answer": result["answer"],
            },
            status=status.HTTP_200_OK,
        )
