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
        # Prefer st.secrets if running in Streamlit Cloud, fallback to os.getenv
        try:
            import streamlit as st
            base_url = st.secrets.get("ENDEE_BASE_URL", os.getenv("ENDEE_BASE_URL", "http://localhost:8080/api/v1"))
            auth_token = st.secrets.get("ENDEE_AUTH_TOKEN", os.getenv("ENDEE_AUTH_TOKEN", ""))
        except Exception:
            base_url = os.getenv("ENDEE_BASE_URL", "http://localhost:8080/api/v1")
            auth_token = os.getenv("ENDEE_AUTH_TOKEN", "")

        _client = Endee()
        if auth_token:
            _client.set_auth_token(auth_token)
        
        # Always set base URL to avoid ambiguity with defaults
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


from rag import vector_mapper

def store_embeddings(repo_id: str, vectors: List[Dict[str, Any]], batch_size: int = 500) -> int:
    """
    Upserts a list of embedding vectors with metadata into the Endee index in batches.

    Args:
        repo_id (str): The repository ID for metadata mapping.
        vectors (List[Dict[str, Any]]): Output from `generate_embeddings()`.
            Each item must contain 'embedding', 'file_path', 'content', 'chunk_index', and 'total_chunks'.
        batch_size (int): Max number of vectors to send in a single batch. Endee limit is 1000.

    Returns:
        int: Number of vectors stored.
    """
    if not vectors:
        logger.warning("No vectors provided to store_embeddings.")
        return 0

    index = _get_index()

    items = []
    for v in vectors:
        meta = vector_mapper.generate_chunk_metadata(
            repo_id=repo_id,
            file_path=v["file_path"],
            chunk_index=v["chunk_index"],
            total_chunks=v["total_chunks"],
            content=v["content"]
        )
        chunk_id = vector_mapper.generate_chunk_id(v["file_path"], v["chunk_index"])
        items.append(vector_mapper.build_vector_payload(chunk_id, v["embedding"], meta))

    total_stored = 0
    logger.info(f"Storing {len(items)} vectors in batches of {batch_size}...")
    
    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]
        index.upsert(batch)
        total_stored += len(batch)
        logger.info(f"  Batch {i//batch_size + 1}: Stored {total_stored}/{len(items)} vectors")

    return total_stored


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
        # Handle results as dictionaries (default for Endee Python SDK)
        meta = item.get("meta", {}) if isinstance(item, dict) else getattr(item, "meta", {})
        item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
        similarity = item.get("similarity") if isinstance(item, dict) else getattr(item, "similarity", None)
        
        results.append({
            "chunk_id": meta.get("chunk_id", item_id),
            "file_path": meta.get("file_path", ""),
            "content": meta.get("content", ""),
            "similarity": similarity,
        })

    logger.info(f"Found {len(results)} results.")
    return results


def delete_vectors_by_file(repo_id: str, file_path: str) -> int:
    """
    Deletes all vectors associated with a specific file in a repository.
    """
    index = _get_index()
    
    # Endee supports metadata filtering in queries. 
    # We query for IDs first, then delete.
    logger.info(f"Deleting vectors for file '{file_path}' in repo '{repo_id}'...")
    
    # This assumes the Endee Python SDK query can take a filter or we just query enough top_k
    # For now, we query with a high top_k to find all chunks of the file.
    # In a real scenario, we'd use a filter if supported by the SDK.
    raw_results = index.query(vector=[0]*EMBEDDING_DIMENSION, top_k=1000) # Dummy vector since we want metadata matches
    
    ids_to_delete = []
    for item in raw_results:
        meta = item.get("meta", {}) if isinstance(item, dict) else getattr(item, "meta", {})
        if meta.get("file_path") == file_path:
             item_id = item.get("id") if isinstance(item, dict) else getattr(item, "id", None)
             if item_id:
                 ids_to_delete.append(item_id)
                 
    if ids_to_delete:
        index.delete(ids=ids_to_delete)
        logger.info(f"Deleted {len(ids_to_delete)} vectors for {file_path}")
        return len(ids_to_delete)
    
    logger.info(f"No vectors found for {file_path}")
    return 0
