import logging
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

MODEL_NAME = "all-MiniLM-L6-v2"

# Load model once at module level to avoid reloading on each call
_model: SentenceTransformer | None = None


def _get_model() -> SentenceTransformer:
    """Lazily loads and caches the SentenceTransformer model."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def generate_embeddings(
    chunks: List[Dict[str, Any]],
    batch_size: int = 64,
    show_progress: bool = False,
) -> List[Dict[str, Any]]:
    """
    Generates embeddings for a list of code chunks using sentence-transformers.

    Args:
        chunks (List[Dict[str, Any]]): A list of chunk dicts containing at least
            'content', 'file_path', and 'chunk_id' keys.
        batch_size (int): Number of chunks to encode in a single batch.
        show_progress (bool): Whether to show a progress bar during encoding.

    Returns:
        List[Dict[str, Any]]: The original chunks with an added 'embedding' key
            containing the vector (a Python list of floats).
    """
    if not chunks:
        logger.warning("No chunks provided to generate_embeddings.")
        return []

    model = _get_model()

    # Extract text content for batch encoding
    texts = [chunk["content"] for chunk in chunks]

    logger.info(f"Generating embeddings for {len(texts)} chunks (batch_size={batch_size})...")

    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )

    results = []
    for chunk, vector in zip(chunks, vectors):
        # Preserve all original keys and add the embedding
        new_chunk = chunk.copy()
        new_chunk["embedding"] = vector.tolist()
        results.append(new_chunk)

    logger.info(f"Embeddings generated for {len(results)} chunks.")
    return results
