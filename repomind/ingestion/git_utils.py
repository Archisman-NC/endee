import subprocess
import logging
import os
from typing import List, Optional

logger = logging.getLogger(__name__)

def get_latest_commit_hash(repo_path: str) -> Optional[str]:
    """
    Returns the latest commit hash (HEAD) for the repository.
    """
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return None
        
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception as e:
        logger.warning(f"Failed to get git commit hash: {e}")
        return None

def get_changed_files(repo_path: str, last_commit: Optional[str] = None) -> List[str]:
    """
    Returns a list of files changed since the last_commit.
    If last_commit is None, it returns files changed in the last commit (HEAD~1..HEAD).
    """
    if not os.path.exists(os.path.join(repo_path, ".git")):
        return []
        
    try:
        # If we have a last commit, diff against it.
        # Otherwise, if it's the first run, we want ALL tracked files.
        if last_commit:
            result = subprocess.run(
                ["git", "diff", "--name-only", last_commit, "HEAD"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
        else:
            # First run: get all files tracked by git
            result = subprocess.run(
                ["git", "ls-files"],
                cwd=repo_path,
                capture_output=True,
                text=True,
                check=True
            )
            
        files = result.stdout.strip().split("\n")
        return [f for f in files if f]
    except Exception as e:
        logger.warning(f"Failed to get changed files via git: {e}")
        return []

def is_git_repo(repo_path: str) -> bool:
    """Checks if the path is a git repository."""
    return os.path.exists(os.path.join(repo_path, ".git"))
