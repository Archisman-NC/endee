import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_chunk_id(file_path: str, index: int) -> str:
    """
    Generates a deterministic and unique ID for a code chunk.
    Format: <file_path>::chunk_<index>
    """
    return f"{file_path}::chunk_{index}"

def generate_chunk_metadata(
    repo_id: str,
    file_path: str,
    chunk_index: int,
    total_chunks: int,
    content: str
) -> Dict[str, Any]:
    """
    Builds a standard metadata dictionary for a code chunk.
    """
    return {
        "repo_id": repo_id,
        "file_path": file_path,
        "chunk_id": generate_chunk_id(file_path, chunk_index),
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "content": content
    }

def build_vector_payload(
    chunk_id: str,
    embedding: list[float],
    metadata: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Format the payload for Endee upsert.
    """
    return {
        "id": chunk_id,
        "vector": embedding,
        "meta": metadata
    }
