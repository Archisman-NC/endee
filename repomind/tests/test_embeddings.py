import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.embeddings import generate_embeddings

# Create sample mock chunks (no need to clone a repo for this test)
SAMPLE_CHUNKS = [
    {
        "content": "def add(a, b):\n    return a + b",
        "file_path": "sample/math_utils.py",
        "chunk_id": str(uuid.uuid4()),
    },
    {
        "content": "class Greeter:\n    def greet(self, name):\n        return f'Hello, {name}!'",
        "file_path": "sample/greeter.py",
        "chunk_id": str(uuid.uuid4()),
    },
    {
        "content": "import os\nimport sys\n\nif __name__ == '__main__':\n    print('Hello, World!')",
        "file_path": "sample/main.py",
        "chunk_id": str(uuid.uuid4()),
    },
]

if __name__ == "__main__":
    print(f"Testing generate_embeddings with {len(SAMPLE_CHUNKS)} sample chunks...\n")

    results = generate_embeddings(SAMPLE_CHUNKS, show_progress=True)

    embedding_dim = len(results[0]["embedding"])
    print(f"\nEmbedding dimension: {embedding_dim}")
    print(f"Embeddings generated successfully for {len(results)} chunks.")

    # Sanity checks
    assert embedding_dim == 384, f"Expected 384, got {embedding_dim}"
    assert len(results) == len(SAMPLE_CHUNKS)
    for r in results:
        assert "embedding" in r
        assert "content" in r
        assert "file_path" in r
        assert "chunk_id" in r

    print("\nAll assertions passed.")
