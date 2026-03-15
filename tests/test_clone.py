import os
import sys

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.github_loader import clone_repo
from ingestion.code_chunker import chunk_code_repository

if __name__ == "__main__":
    repo_url = "https://github.com/pallets/flask"
    destination = os.path.join(os.path.dirname(__file__), 'test_repos', 'flask')
    
    print(f"Testing clone of {repo_url} into {destination}...")
    try:
        path = clone_repo(repo_url, destination)
        print(f"Repository cloned successfully into {path}\n")
        
        print("Testing code chunking...")
        chunks = chunk_code_repository(path)
        print(f"Total chunks generated: {len(chunks)}")
        
        if chunks:
            print("\nSample chunk 1:")
            print(chunks[0])
            
            print("\nSample chunk 2:")
            print(chunks[len(chunks) // 2])
            
    except Exception as e:
        print(f"Failed during testing: {e}")
