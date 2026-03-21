import os
import logging
from typing import Dict, List, Any
from ingestion import file_tracker
from ingestion import git_utils
from ingestion.code_chunker import SUPPORTED_EXTENSIONS

logger = logging.getLogger(__name__)

def get_current_file_hashes(repo_path: str, include_files: List[str] = None) -> Dict[str, str]:
    """
    Scans the repository (or specific files) and computes SHA-256 hashes.
    """
    current_hashes = {}
    
    if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
        logger.error(f"Invalid repository path: {repo_path}")
        return current_hashes

    # If include_files is provided, we only check those. Otherwise we walk the whole repo.
    if include_files is not None:
        for rel_path in include_files:
            abs_path = os.path.join(repo_path, rel_path)
            if os.path.exists(abs_path) and os.path.isfile(abs_path):
                _, ext = os.path.splitext(rel_path)
                if ext.lower() in SUPPORTED_EXTENSIONS:
                    try:
                        with open(abs_path, 'r', encoding='utf-8') as f:
                            current_hashes[rel_path] = file_tracker.compute_file_hash(f.read())
                    except Exception:
                        continue
        return current_hashes

    # Full scan fallback
    for root, _, files in os.walk(repo_path):
        if any(part.startswith('.') for part in root.split(os.sep)) or 'node_modules' in root or '__pycache__' in root:
            continue
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() not in SUPPORTED_EXTENSIONS:
                continue
            file_path = os.path.join(root, file)
            rel_path = os.path.relpath(file_path, repo_path)
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    current_hashes[rel_path] = file_tracker.compute_file_hash(f.read())
            except Exception:
                continue
    return current_hashes

def detect_changes(repo_id: str, repo_path: str) -> Dict[str, Any]:
    """
    Compares the current repository state against the stored index.
    Uses Git optimizations if available.
    """
    results = {"new": [], "modified": [], "deleted": [], "unchanged": [], "status": "ok"}
    
    # 1. Load previous state
    old_index = file_tracker.load_index(repo_id)
    old_hashes = {path: data["hash"] for path, data in old_index.items() if not path.startswith("_")}
    metadata = file_tracker.get_repo_metadata(repo_id)
    last_commit = metadata.get("last_commit")
    
    # 2. Check for Git Early Exit
    if git_utils.is_git_repo(repo_path):
        current_commit = git_utils.get_latest_commit_hash(repo_path)
        if last_commit and current_commit == last_commit:
            logger.info(f"[RepoMind] No changes detected (Commit {current_commit[:7]}).")
            results["status"] = "skipped"
            return results
        
        # Fast path: Use git diff to find candidates
        logger.info(f"[RepoMind] Detected commit change: {last_commit[:7] if last_commit else 'None'} -> {current_commit[:7]}")
        git_files = git_utils.get_changed_files(repo_path, last_commit)
        logger.info(f"[RepoMind] Git detected {len(git_files)} potentially changed files.")
        
        # We only need to hash the files git mentioned + check for deleted in those
        current_hashes = get_current_file_hashes(repo_path, include_files=git_files)
        
        # For Git mode, we must also consider files in the old index that might have been deleted/moved
        # BUT Git diff --name-only usually includes deletions.
    else:
        # Full scan fallback for non-git or first run without git
        logger.info("[RepoMind] Git not available. Falling back to full hash scan.")
        current_hashes = get_current_file_hashes(repo_path)

    # 3. Hybrid Classification logic
    # Check current files (either full or git-filtered)
    all_known_paths = set(old_hashes.keys()) | set(current_hashes.keys())
    
    for path in all_known_paths:
        if path not in old_hashes:
            if os.path.exists(os.path.join(repo_path, path)):
                results["new"].append(path)
        elif path not in current_hashes:
            # If we used git filter, and path is in old_index but NOT in current_hashes,
            # it might be unchanged (skipped by git) or deleted.
            if git_utils.is_git_repo(repo_path) and path not in git_files:
                results["unchanged"].append(path)
            elif not os.path.exists(os.path.join(repo_path, path)):
                results["deleted"].append(path)
            else:
                # This case shouldn't happen with full scan, but with git it means it was filtered out (unchanged)
                results["unchanged"].append(path)
        else:
            if current_hashes[path] != old_hashes[path]:
                results["modified"].append(path)
            else:
                results["unchanged"].append(path)
                
    return results
