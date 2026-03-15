import logging
import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from endee import Endee, Precision

load_dotenv()

logger = logging.getLogger(__name__)

# Index configuration
INDEX_NAME = "repomind"
EMBEDDING_DIMENSION = 384  # all-MiniLM-L6-v2 output dimension
SPACE_TYPE = "cosine"

_client: Optional[Endee] = None
_index = None


def _get_client() -> Endee:
    """Lazily creates and caches the Endee client."""
    global _client
    if _client is None:
        base_url = os.getenv("ENDEE_BASE_URL", "http://localhost:8080/api/v1")
        auth_token = os.getenv("ENDEE_AUTH_TOKEN", "")
        _client = Endee()
        if auth_token:
            _client.set_auth_token(auth_token)
        if base_url != "http://localhost:8080/api/v1":
            _client.set_base_url(base_url)
        logger.info(f"Endee client initialized → {base_url}")
    return _client


def _get_index():
    """Lazily retrieves (or creates) the Endee index."""
    global _index
    if _index is not None:
        return _index

    client = _get_client()
    
    # Try to get existing index first; create if not found
    try:
        _index = client.get_index(name=INDEX_NAME)
        logger.info(f"Connected to existing Endee index '{INDEX_NAME}'.")
    except Exception:
        logger.info(f"Index '{INDEX_NAME}' not found. Creating...")
        client.create_index(
            name=INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            space_type=SPACE_TYPE,
            precision=Precision.INT8,
        )
        _index = client.get_index(name=INDEX_NAME)
        logger.info(f"Created new Endee index '{INDEX_NAME}'.")

    return _index


def store_embeddings(vectors: List[Dict[str, Any]]) -> int:
    """
    Upserts a list of embedding vectors with metadata into the Endee index.

    Args:
        vectors (List[Dict[str, Any]]): Output from `generate_embeddings()`.
            Each item must contain 'chunk_id', 'embedding', 'file_path', and 'content'.

    Returns:
        int: Number of vectors stored.

    Raises:
        Exception: If the upsert operation fails.
    """
    if not vectors:
        logger.warning("No vectors provided to store_embeddings.")
        return 0

    index = _get_index()

    items = [
        {
            "id": v["chunk_id"],
            "vector": v["embedding"],
            "meta": {
                "file_path": v["file_path"],
                "chunk_id": v["chunk_id"],
                "content": v["content"],
            },
        }
        for v in vectors
    ]

    logger.info(f"Storing {len(items)} vectors in index '{INDEX_NAME}'...")
    index.upsert(items)
    logger.info(f"Successfully stored {len(items)} vectors.")
    return len(items)


def search_similar(
    query_vector: List[float],
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Searches for the most similar vectors to the given query vector.

    Args:
        query_vector (List[float]): The query embedding vector (dimension 384).
        top_k (int): Number of top results to return. Defaults to 5.

    Returns:
        List[Dict[str, Any]]: A list of matched chunks, each with:
            - 'chunk_id': unique identifier
            - 'file_path': source file location
            - 'content': code content
            - 'similarity': cosine similarity score
    """
    index = _get_index()

    logger.info(f"Searching for top {top_k} similar chunks...")
    raw_results = index.query(vector=query_vector, top_k=top_k)

    results = []
    for item in raw_results:
        meta = item.meta if hasattr(item, "meta") and item.meta else {}
        results.append({
            "chunk_id": meta.get("chunk_id", item.id),
            "file_path": meta.get("file_path", ""),
            "content": meta.get("content", ""),
            "similarity": item.similarity if hasattr(item, "similarity") else None,
        })

    logger.info(f"Found {len(results)} results.")
    return results
