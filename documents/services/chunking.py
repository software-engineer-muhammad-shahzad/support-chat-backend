from langchain_text_splitters import RecursiveCharacterTextSplitter

from documents.models import DocumentChunk


def split_text(text):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    return splitter.split_text(text)


def save_chunks(document, chunks):
    DocumentChunk.objects.bulk_create(
        [
            DocumentChunk(
                document=document,
                content=chunk,
                chunk_index=index,
            )
            for index, chunk in enumerate(chunks)
        ]
    )