import os
import sys
import uuid

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.embeddings import generate_embeddings
from rag.vector_store import store_embeddings
from rag.retriever import retrieve_relevant_chunks

# Seed the vector store with authentication-related code chunks
SEED_CHUNKS = [
    {
        "content": (
            "def authenticate_user(token: str) -> bool:\n"
            "    \"\"\"Validates a bearer token against the auth service.\"\"\"\n"
            "    return verify_jwt(token)"
        ),
        "file_path": "src/auth.py",
        "chunk_id": str(uuid.uuid4()),
    },
    {
        "content": (
            "def verify_jwt(token: str) -> bool:\n"
            "    try:\n"
            "        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])\n"
            "        return True\n"
            "    except jwt.ExpiredSignatureError:\n"
            "        return False"
        ),
        "file_path": "src/auth.py",
        "chunk_id": str(uuid.uuid4()),
    },
    {
        "content": (
            "class UserRepository:\n"
            "    def get_user(self, user_id: str):\n"
            "        return self.db.query(User).filter(User.id == user_id).first()"
        ),
        "file_path": "src/users.py",
        "chunk_id": str(uuid.uuid4()),
    },
    {
        "content": (
            "def calculate_distance(p1, p2):\n"
            "    return math.sqrt((p2.x - p1.x)**2 + (p2.y - p1.y)**2)"
        ),
        "file_path": "src/geometry.py",
        "chunk_id": str(uuid.uuid4()),
    },
]

if __name__ == "__main__":
    print("Step 1: Seeding vector store with sample code chunks...")
    vectors = generate_embeddings(SEED_CHUNKS, show_progress=False)
    stored = store_embeddings(vectors)
    print(f"  Stored {stored} chunks.\n")

    query = "How does authentication work?"
    print(f"Step 2: Running query → '{query}'")
    results = retrieve_relevant_chunks(query, top_k=5)

    print(f"\nRetrieved {len(results)} chunks:\n")
    for i, r in enumerate(results, 1):
        sim = f"{r['similarity']:.4f}" if r.get("similarity") is not None else "N/A"
        print(f"  [{i}] {r['file_path']}  (similarity={sim})")
        print(f"      {r['content'][:80].strip()}...")
        print()

    # Check that results from auth.py appear
    auth_results = [r for r in results if "auth" in r.get("file_path", "")]
    print(f"Chunks from auth.py in results: {len(auth_results)}")
    assert len(auth_results) > 0, "Expected at least one result from auth.py"
    print("Test passed: Retrieved chunks from auth.py.")
