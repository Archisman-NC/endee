import os
import sys

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.github_loader import clone_repo
from ingestion.code_chunker import chunk_code_repository

if __name__ == "__main__":
    repo_url = "https://github.com/pallets/flask"
    destination = os.path.join(os.path.dirname(__file__), 'test_repos', 'flask')
    
    print("Setting up test repository...")
    path = clone_repo(repo_url, destination)
    
    print("Executing chunking...")
    chunks = chunk_code_repository(path)
    
    print(f"Total chunks generated: {len(chunks)}")
    if len(chunks) >= 100:
        print("Success: Generated 100+ chunks.")
    else:
        print("Warning: Expected 100+, got fewer.")
