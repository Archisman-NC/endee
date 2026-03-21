import os
import tempfile
import logging
from typing import Dict, Any, Optional

from ingestion import github_loader
from ingestion import code_chunker
from ingestion import delta_detector
from ingestion import file_tracker
from ingestion import git_utils
from ingestion import task_manager
from rag import embeddings
from rag import vector_store

logger = logging.getLogger(__name__)

def run_indexing_pipeline(repo_url: str, progress_callback=None) -> Dict[str, Any]:
    """
    Executes the full indexing pipeline for the given repository URL.
    progress_callback: A function(progress_int, message_str, append_log_str=None)
    """
    repo_url = repo_url.strip()
    logger.info(f"[RepoMind] Background indexing started for {repo_url}")
    
    def _update(prog, msg, log=None):
        task_manager.update_task(repo_url, progress=prog, message=msg, append_log=log)
        if progress_callback:
            progress_callback(prog, msg, log)

    _update(5, "Initializing pipeline...", "⏳ Initializing indexing pipeline...")
    
    results = {
        "status": "error",
        "new_count": 0,
        "modified_count": 0,
        "deleted_count": 0,
        "inserted_vectors": 0,
        "error": None
    }
    
    try:
        # 1. Clone/Update Repo
        _update(10, "Cloning repository...", "⏳ Cloning repository from GitHub...")
        dest = os.path.join(tempfile.gettempdir(), "repomind_repos",
                            repo_url.rstrip("/").split("/")[-1])
        repo_path = github_loader.clone_repo(repo_url, dest)
        _update(20, "Detecting changes...", "✔ Repository cloned successfully.")
        
        # 2. Detect Changes
        _update(25, "Detecting changes...", "⏳ Comparing local state with indexed hashes...")
        changes = delta_detector.detect_changes(repo_url, repo_path)
        
        if changes.get("status") == "skipped":
            logger.info(f"[RepoMind] No changes detected for {repo_url}. Skipping.")
            task_manager.update_task(repo_url, status="completed", progress=100, 
                                     message="Repository up to date.",
                                     append_log="✔ No changes detected. Skipping re-indexing.")
            if progress_callback:
                progress_callback(100, "Repository up to date.", "✔ No changes detected.")
            return {"status": "skipped"}
            
        results["new_count"] = len(changes["new"])
        results["modified_count"] = len(changes["modified"])
        results["deleted_count"] = len(changes["deleted"])
        _update(30, "Detecting changes...", 
                f"✔ Changes detected: {len(changes['new'])} new, {len(changes['modified'])} modified, {len(changes['deleted'])} deleted.")
        
        # 3. Handle Deletions
        if changes["deleted"]:
            _update(35, "Cleaning up deleted files...", f"⏳ Removing vectors for {len(changes['deleted'])} deleted files...")
            for f in changes["deleted"]:
                vector_store.delete_vectors_by_file(repo_url, f)
                file_tracker.remove_file_record(repo_url, f)
            _update(40, "Cleaning up deleted files...", "✔ Deleted file cleanup complete.")
                
        # 4. Handle Modified/New
        files_to_process = changes["new"] + changes["modified"]
        if files_to_process:
            # Purge stale vectors for modified files
            if changes["modified"]:
                _update(45, "Purging modified files...", f"⏳ Purging stale vectors for {len(changes['modified'])} modified files...")
                for f in changes["modified"]:
                    vector_store.delete_vectors_by_file(repo_url, f)
                _update(50, "Purging modified files...", "✔ Stale vector purge complete.")
            
            # Chunking
            _update(55, "Processing files...", f"⏳ Chunking {len(files_to_process)} changed files...")
            chunks = code_chunker.chunk_code_repository(repo_path, include_files=files_to_process)
            _update(65, "Processing files...", f"✔ Created {len(chunks)} code chunks.")
            
            if chunks:
                # Embeddings
                _update(70, "Generating embeddings...", f"⏳ Generating embeddings for {len(chunks)} chunks...")
                vectors = embeddings.generate_embeddings(chunks)
                _update(85, "Generating embeddings...", "✔ Embeddings generated.")
                
                # Storage
                _update(90, "Storing in database...", "⏳ Storing vectors in Endee database...")
                count = vector_store.store_embeddings(repo_url, vectors)
                results["inserted_vectors"] = count
                _update(95, "Storing in database...", f"✔ Successfully stored {count} vectors.")
                
                # Metadata Updates
                _update(98, "Finalizing indexing...", "⏳ Updating file tracker and commit metadata...")
                for f in files_to_process:
                    abs_f_path = os.path.join(repo_path, f)
                    if os.path.exists(abs_f_path):
                        with open(abs_f_path, 'r', encoding='utf-8') as f_obj:
                            h = file_tracker.compute_file_hash(f_obj.read())
                            file_tracker.update_file_record(repo_url, f, h)
                
                if git_utils.is_git_repo(repo_path):
                    current_commit = git_utils.get_latest_commit_hash(repo_path)
                    if current_commit:
                        file_tracker.update_repo_metadata(repo_url, {"last_commit": current_commit})

        results["status"] = "success"
        task_manager.update_task(repo_url, status="completed", progress=100, 
                                 message="Indexing completed!",
                                 append_log="✔ Indexing pipeline finished successfully.")
        if progress_callback:
            progress_callback(100, "Indexing completed!", "✔ Indexing pipeline finished successfully.")
        logger.info(f"[RepoMind] Background indexing completed for {repo_url}")
        return results

    except Exception as e:
        logger.exception(f"[RepoMind] Indexing failed: {e}")
        task_manager.update_task(repo_url, status="failed", error=str(e), 
                                 message="Indexing failed.",
                                 append_log=f"❌ Error: {str(e)}")
        if progress_callback:
            progress_callback(None, "Indexing failed.", f"❌ Error: {str(e)}", error=str(e))
        results["error"] = str(e)
        raise e # Re-raise for Celery/Retries
