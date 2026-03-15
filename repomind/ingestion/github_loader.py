import os
import logging
from git import Repo
from git.exc import GitCommandError

logger = logging.getLogger(__name__)

def clone_repo(repo_url: str, destination: str) -> str:
    """
    Clones a GitHub repository using GitPython.
    If the repository already exists locally, it skips cloning.
    
    Args:
        repo_url (str): URL of the GitHub repository.
        destination (str): Local path to clone the repository to.
        
    Returns:
        str: The absolute path to the downloaded repository.
        
    Raises:
        GitCommandError: If cloning fails due to a git error.
        Exception: If cloning fails for any other reason.
    """
    try:
        abs_dest = os.path.abspath(destination)
        
        # Check if directory already exists
        if os.path.exists(abs_dest) and os.path.isdir(abs_dest):
            # Verify it's actually a git repository
            if os.path.exists(os.path.join(abs_dest, '.git')):
                logger.info(f"Repository already exists at {abs_dest}. Skipping clone.")
                return abs_dest
            else:
                logger.warning(f"Directory {abs_dest} exists but is not a git repository. Proceeding with clone may fail or overwrite data.")
                
        logger.info(f"Cloning {repo_url} into {abs_dest}...")
        Repo.clone_from(repo_url, abs_dest)
        logger.info(f"Successfully cloned {repo_url}.")
        
        return abs_dest
        
    except GitCommandError as e:
        logger.error(f"Git command error while cloning {repo_url}: {e}")
        raise
    except Exception as e:
        logger.error(f"An unexpected error occurred while cloning {repo_url}: {e}")
        raise
