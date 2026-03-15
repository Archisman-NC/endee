import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag.generator import generate_answer

# Mock retrieved chunks simulating what a retriever would return for a routing query
MOCK_CHUNKS = [
    {
        "content": (
            "from flask import Flask\n"
            "app = Flask(__name__)\n\n"
            "@app.route('/')\n"
            "def index():\n"
            "    return 'Hello, World!'"
        ),
        "file_path": "src/app.py",
        "chunk_id": "chunk-001",
        "similarity": 0.91,
    },
    {
        "content": (
            "@app.route('/users/<int:user_id>', methods=['GET'])\n"
            "def get_user(user_id):\n"
            "    user = UserRepository().get_user(user_id)\n"
            "    return jsonify(user.to_dict())"
        ),
        "file_path": "src/app.py",
        "chunk_id": "chunk-002",
        "similarity": 0.87,
    },
    {
        "content": (
            "@app.route('/login', methods=['POST'])\n"
            "def login():\n"
            "    data = request.get_json()\n"
            "    token = create_jwt(data['username'], data['password'])\n"
            "    return jsonify({'token': token})"
        ),
        "file_path": "src/auth.py",
        "chunk_id": "chunk-003",
        "similarity": 0.82,
    },
]

if __name__ == "__main__":
    query = "Explain how routing works"
    print(f"Query: {query}\n")
    print("Generating answer...\n")

    result = generate_answer(query, MOCK_CHUNKS)

    print("=" * 60)
    print("ANSWER:")
    print("=" * 60)
    print(result["answer"])
    print()
    print("Source files:")
    for f in result["source_files"]:
        print(f"  - {f}")

    assert "answer" in result and len(result["answer"]) > 0
    assert "source_files" in result
    assert "src/app.py" in result["source_files"]
    print("\nAll assertions passed.")
