import os
import json
import hashlib
import logging
from datetime import datetime
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

INDEX_FILE = ".repomind_index.json"

def compute_file_hash(content: str) -> str:
    """Computes a deterministic SHA-256 hash of the file content."""
    return hashlib.sha256(content.encode('utf-8')).hexdigest()

def load_index(repo_id: str) -> Dict[str, Any]:
    """
    Loads the tracking index for a specific repository.
    Returns:
        Dict[str, Any]: File path -> {hash, last_indexed}
    """
    if not os.path.exists(INDEX_FILE):
        return {}
        
    try:
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            full_index = json.load(f)
            return full_index.get(repo_id, {})
    except (json.JSONDecodeError, OSError) as e:
        logger.error(f"Error loading index file: {e}")
        return {}

def save_index(repo_id: str, data: Dict[str, Any]) -> bool:
    """
    Saves the tracking data for a specific repository into the master index file.
    """
    full_index = {}
    
    if os.path.exists(INDEX_FILE):
        try:
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                full_index = json.load(f)
        except (json.JSONDecodeError, OSError):
            logger.warning(f"Failed to read existing index file, starting fresh.")

    full_index[repo_id] = data
    
    try:
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            json.dump(full_index, f, indent=2)
        return True
    except OSError as e:
        logger.error(f"Failed to save index file: {e}")
        return False

def update_file_record(repo_id: str, file_path: str, file_hash: str) -> bool:
    """
    Updates or creates a single file record in the index for the given repo.
    """
    repo_data = load_index(repo_id)
    repo_data[file_path] = {
        "hash": file_hash,
        "last_indexed": datetime.now().isoformat()
    }
    return save_index(repo_id, repo_data)

def remove_file_record(repo_id: str, file_path: str) -> bool:
    """
    Removes a file record from the index for the given repo.
    """
    repo_data = load_index(repo_id)
    if file_path in repo_data:
        del repo_data[file_path]
        return save_index(repo_id, repo_data)
    return False

def get_repo_metadata(repo_id: str) -> Dict[str, Any]:
    """
    Retrieves repository-level metadata (e.g., last_commit).
    """
    repo_data = load_index(repo_id)
    return repo_data.get("_metadata", {})

def update_repo_metadata(repo_id: str, metadata: Dict[str, Any]) -> bool:
    """
    Updates repository-level metadata.
    """
    repo_data = load_index(repo_id)
    if "_metadata" not in repo_data:
        repo_data["_metadata"] = {}
        
    repo_data["_metadata"].update(metadata)
    return save_index(repo_id, repo_data)
