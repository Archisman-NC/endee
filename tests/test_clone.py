import os
import sys

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.github_loader import clone_repo

if __name__ == "__main__":
    repo_url = "https://github.com/pallets/flask"
    destination = os.path.join(os.path.dirname(__file__), 'test_repos', 'flask')
    
    print(f"Testing clone of {repo_url} into {destination}...")
    try:
        path = clone_repo(repo_url, destination)
        print(f"Repository cloned successfully into {path}")
    except Exception as e:
        print(f"Failed to clone repository: {e}")
