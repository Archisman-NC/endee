import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.embeddings import generate_embeddings
from rag.vector_store import store_embeddings, search_similar

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
        "content": "def multiply(a, b):\n    return a * b\n\ndef divide(a, b):\n    if b == 0:\n        raise ValueError('Cannot divide by zero')\n    return a / b",
        "file_path": "sample/math_utils.py",
        "chunk_id": str(uuid.uuid4()),
    },
]

if __name__ == "__main__":
    print("Step 1: Generating embeddings...")
    vectors = generate_embeddings(SAMPLE_CHUNKS, show_progress=False)
    print(f"  Generated {len(vectors)} embeddings (dim={len(vectors[0]['embedding'])})")

    print("\nStep 2: Storing vectors in Endee...")
    count = store_embeddings(vectors)
    print(f"  Vectors stored successfully: {count}")

    print("\nStep 3: Searching for similar chunks...")
    query_vector = vectors[0]["embedding"]  # Use first chunk as query
    results = search_similar(query_vector, top_k=3)
    
    print(f"  Top results retrieved: {len(results)}")
    for i, r in enumerate(results, 1):
        print(f"\n  Result {i}:")
        print(f"    file_path : {r['file_path']}")
        print(f"    chunk_id  : {r['chunk_id']}")
        print(f"    similarity: {r['similarity']:.4f}" if r['similarity'] is not None else "    similarity: N/A")
        print(f"    content   : {r['content'][:60]}...")
