import logging
from typing import List, Dict, Any
from rag.embeddings import generate_embeddings
from rag.vector_store import search_similar

logger = logging.getLogger(__name__)


def retrieve_relevant_chunks(
    query: str,
    top_k: int = 5,
) -> List[Dict[str, Any]]:
    """
    Retrieves the most relevant code chunks for a given natural language query.

    Steps:
      1. Converts the query string into an embedding vector.
      2. Searches the Endee vector database for the top-K nearest neighbors.
      3. Returns matched chunks with their metadata.

    Args:
        query (str): The natural language query (e.g. "How does authentication work?").
        top_k (int): Number of top results to return. Defaults to 5.

    Returns:
        List[Dict[str, Any]]: A list of the most relevant chunks, each containing:
            - 'content'    : the code snippet
            - 'file_path'  : source file location
            - 'chunk_id'   : unique identifier
            - 'similarity' : cosine similarity score (float)
    """
    if not query or not query.strip():
        logger.warning("Empty query passed to retrieve_relevant_chunks.")
        return []

    logger.info(f"Retrieving top {top_k} chunks for query: '{query}'")

    # Step 1: Embed the query
    query_chunk = [{"content": query, "file_path": "", "chunk_id": "query"}]
    embedded = generate_embeddings(query_chunk)
    if not embedded:
        logger.error("Failed to generate embedding for query.")
        return []
    query_vector = embedded[0]["embedding"]

    # Step 2 & 3: Search the vector DB and return results
    results = search_similar(query_vector, top_k=top_k)

    logger.info(f"Retrieved {len(results)} chunks.")
    return results
