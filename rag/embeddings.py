"""
rag/embeddings.py — Vector store construction and loading.

Sprint 3: swapped VoyageAIEmbeddings → OpenAIEmbeddings (text-embedding-3-small).
Everything else (Chroma load/build logic) is identical to Sprint 2.
"""

import logging
from pathlib import Path

from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from rag.loader import load_and_split
from config import (
    OPENAI_API_KEY,
    EMBEDDING_MODEL,
    CHROMA_DB_PATH,
    CHROMA_COLLECTION_NAME,
)

logger = logging.getLogger(__name__)


def get_or_create_vector_store() -> Chroma:
    """
    If ChromaDB already exists on disk, load it.
    If not, build it from the source PDFs.
    """
    chroma_path = Path(CHROMA_DB_PATH)
    if chroma_path.exists() and any(chroma_path.iterdir()):
        logger.info("Vector store found on disk → loading...")
        return _load_vector_store()
    logger.info("No vector store found → building from documents...")
    return _build_vector_store()


def _load_vector_store() -> Chroma:
    logger.info(f"Loading existing vector store from {CHROMA_DB_PATH}")
    return Chroma(
        collection_name=CHROMA_COLLECTION_NAME,
        embedding_function=_get_embeddings(),
        persist_directory=CHROMA_DB_PATH,
    )


def _build_vector_store(docs_path: str = None) -> Chroma:
    logger.info("Building vector store from documents...")
    chunks       = load_and_split(docs_path) if docs_path else load_and_split()
    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=_get_embeddings(),
        collection_name=CHROMA_COLLECTION_NAME,
        persist_directory=CHROMA_DB_PATH,
    )
    logger.info(f"Vector store built with {len(chunks)} chunks → saved to {CHROMA_DB_PATH}")
    return vector_store


def _get_embeddings() -> OpenAIEmbeddings:
    return OpenAIEmbeddings(
        model=EMBEDDING_MODEL,        # "text-embedding-3-small" — set in config.py
        openai_api_key=OPENAI_API_KEY,
    )
