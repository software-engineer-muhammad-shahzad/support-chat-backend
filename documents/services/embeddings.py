from documents.models import DocumentChunk
from documents.services.genai_client import client

# embed_content takes a list of texts and returns one embedding per text in
# a single API call — verified directly (3 texts in, 3 embeddings out, one
# request). Batching a document's chunks this way instead of one call per
# chunk cuts a many-chunk document down to a handful of round-trips, which
# matters more now that ingestion runs as a Celery task: fewer, larger
# calls means less time held open per task and less pressure on Gemini's
# free-tier rate limit. Capped rather than unbounded in case a very large
# document ends up with far more chunks than is sensible to embed at once.
EMBEDDING_BATCH_SIZE = 100


def generate_embedding(text):
    """Embed a single piece of text — what retrieval.py uses for the
    incoming question, which is always exactly one string."""
    return generate_embeddings([text])[0]


def generate_embeddings(texts):
    """Embed a batch of texts in as few API calls as EMBEDDING_BATCH_SIZE
    allows. Order is preserved: embeddings[i] corresponds to texts[i]."""
    embeddings = []
    for start in range(0, len(texts), EMBEDDING_BATCH_SIZE):
        batch = texts[start : start + EMBEDDING_BATCH_SIZE]
        response = client.models.embed_content(
            model="gemini-embedding-001",
            contents=batch,
            config={
                "output_dimensionality": 1536,
            },
        )
        embeddings.extend(e.values for e in response.embeddings)
    return embeddings


def embed_document(document):
    """Embeds every chunk of `document` that doesn't have one yet — safe
    to call again on a partially-embedded document (e.g. after
    ingest_document_task retries): already-embedded chunks are excluded by
    the query, never re-embedded.

    Saves each batch to the database as soon as *that* batch's API call
    succeeds, rather than accumulating every batch in memory and saving
    only once all of them are done. That matters the moment a document has
    more chunks than EMBEDDING_BATCH_SIZE: with the accumulate-then-save
    approach, a failure on batch 2 discarded batch 1's already-computed
    embeddings too (they were never persisted), so a retry re-embedded
    everything from scratch — including the chunks that succeeded the
    first time. Saving per-batch means a retry only ever redoes the
    chunks that actually still need it.
    """
    chunks = list(
        DocumentChunk.objects.filter(
            document=document,
            embedding__isnull=True,
        )
    )
    if not chunks:
        return 0

    embedded_count = 0
    for start in range(0, len(chunks), EMBEDDING_BATCH_SIZE):
        batch = chunks[start : start + EMBEDDING_BATCH_SIZE]
        embeddings = generate_embeddings([chunk.content for chunk in batch])
        for chunk, embedding in zip(batch, embeddings):
            chunk.embedding = embedding
            chunk.save(update_fields=["embedding"])
        embedded_count += len(batch)

    return embedded_count
