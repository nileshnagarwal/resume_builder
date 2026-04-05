"""ChromaDB wrapper for the Master Resume vector store."""

from typing import Optional

import chromadb

from src.config import CHROMA_DB_DIR, MASTER_RESUME_DIR


COLLECTION_NAME = "master_resume"


def get_client() -> chromadb.PersistentClient:
    """Return a persistent ChromaDB client."""
    return chromadb.PersistentClient(path=str(CHROMA_DB_DIR))


def get_or_create_collection(
    client: Optional[chromadb.PersistentClient] = None,
) -> chromadb.Collection:
    """Get or create the master_resume collection."""
    if client is None:
        client = get_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)


def load_master_resume() -> str:
    """Read the master resume markdown file and return its full text."""
    resume_files = list(MASTER_RESUME_DIR.glob("*.md"))
    if not resume_files:
        raise FileNotFoundError(
            f"No .md files found in {MASTER_RESUME_DIR}"
        )
    # Use the most recently modified file
    latest = max(resume_files, key=lambda f: f.stat().st_mtime)
    return latest.read_text(encoding="utf-8")


def query_similar(query_text: str, n_results: int = 5) -> list[dict]:
    """Query the vector DB for chunks similar to the given text.

    Returns a list of dicts with 'document' and 'metadata' keys.
    """
    collection = get_or_create_collection()
    results = collection.query(
        query_texts=[query_text],
        n_results=n_results,
    )
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    return [
        {"document": doc, "metadata": meta}
        for doc, meta in zip(documents, metadatas)
    ]


def add_entry(text: str, metadata: Optional[dict] = None) -> None:
    """Add a new entry to the master resume vector DB."""
    collection = get_or_create_collection()
    doc_id = f"entry_{collection.count()}"
    collection.add(
        documents=[text],
        metadatas=[metadata or {}],
        ids=[doc_id],
    )


def ingest_master_resume() -> int:
    """Split the master resume into chunks and ingest into ChromaDB.

    Returns the number of chunks ingested.
    """
    text = load_master_resume()
    chunks = _split_into_chunks(text)
    collection = get_or_create_collection()

    # Clear existing data and re-ingest
    existing = collection.count()
    if existing > 0:
        all_ids = collection.get()["ids"]
        if all_ids:
            collection.delete(ids=all_ids)

    ids = [f"chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": "master_resume", "chunk_index": i} for i in range(len(chunks))]
    collection.add(documents=chunks, ids=ids, metadatas=metadatas)
    return len(chunks)


def _split_into_chunks(text: str, chunk_size: int = 500) -> list[str]:
    """Split text into chunks by paragraph boundaries, respecting chunk_size.

    Tries to keep logical sections together by splitting on double newlines.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    current_chunk = ""

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current_chunk) + len(para) + 2 > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk = f"{current_chunk}\n\n{para}" if current_chunk else para

    if current_chunk.strip():
        chunks.append(current_chunk.strip())

    return chunks
