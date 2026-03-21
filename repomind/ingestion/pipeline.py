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

def run_indexing_pipeline(repo_url: str) -> Dict[str, Any]:
    """
    Executes the full indexing pipeline for the given repository URL.
    """
    repo_url = repo_url.strip()
    logger.info(f"[RepoMind] Background indexing started for {repo_url}")
    
    task_manager.update_task(repo_url, status="running", progress=5, 
                             message="Initializing pipeline...",
                             append_log="⏳ Initializing indexing pipeline...")
    
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
        task_manager.update_task(repo_url, progress=10, message="Cloning repository...",
                                 append_log="⏳ Cloning repository from GitHub...")
        dest = os.path.join(tempfile.gettempdir(), "repomind_repos",
                            repo_url.rstrip("/").split("/")[-1])
        repo_path = github_loader.clone_repo(repo_url, dest)
        task_manager.update_task(repo_url, progress=20, append_log="✔ Repository cloned successfully.")
        
        # 2. Detect Changes
        task_manager.update_task(repo_url, progress=25, message="Detecting changes...",
                                 append_log="⏳ Comparing local state with indexed hashes...")
        changes = delta_detector.detect_changes(repo_url, repo_path)
        
        if changes.get("status") == "skipped":
            logger.info(f"[RepoMind] No changes detected for {repo_url}. Skipping.")
            task_manager.update_task(repo_url, status="completed", progress=100, 
                                     message="Repository up to date.",
                                     append_log="✔ No changes detected. Skipping re-indexing.")
            return {"status": "skipped"}
            
        results["new_count"] = len(changes["new"])
        results["modified_count"] = len(changes["modified"])
        results["deleted_count"] = len(changes["deleted"])
        task_manager.update_task(repo_url, progress=30, 
                                 append_log=f"✔ Changes detected: {len(changes['new'])} new, {len(changes['modified'])} modified, {len(changes['deleted'])} deleted.")
        
        # 3. Handle Deletions
        if changes["deleted"]:
            task_manager.update_task(repo_url, progress=35, message="Cleaning up deleted files...",
                                     append_log=f"⏳ Removing vectors for {len(changes['deleted'])} deleted files...")
            for f in changes["deleted"]:
                vector_store.delete_vectors_by_file(repo_url, f)
                file_tracker.remove_file_record(repo_url, f)
            task_manager.update_task(repo_url, progress=40, append_log="✔ Deleted file cleanup complete.")
                
        # 4. Handle Modified/New
        files_to_process = changes["new"] + changes["modified"]
        if files_to_process:
            # Purge stale vectors for modified files
            if changes["modified"]:
                task_manager.update_task(repo_url, progress=45, message="Purging modified files...",
                                         append_log=f"⏳ Purging stale vectors for {len(changes['modified'])} modified files...")
                for f in changes["modified"]:
                    vector_store.delete_vectors_by_file(repo_url, f)
                task_manager.update_task(repo_url, progress=50, append_log="✔ Stale vector purge complete.")
            
            # Chunking
            task_manager.update_task(repo_url, progress=55, message="Processing files...",
                                     append_log=f"⏳ Chunking {len(files_to_process)} changed files...")
            chunks = code_chunker.chunk_code_repository(repo_path, include_files=files_to_process)
            task_manager.update_task(repo_url, progress=65, append_log=f"✔ Created {len(chunks)} code chunks.")
            
            if chunks:
                # Embeddings
                task_manager.update_task(repo_url, progress=70, message="Generating embeddings...",
                                         append_log=f"⏳ Generating embeddings for {len(chunks)} chunks...")
                vectors = embeddings.generate_embeddings(chunks)
                task_manager.update_task(repo_url, progress=85, append_log="✔ Embeddings generated.")
                
                # Storage
                task_manager.update_task(repo_url, progress=90, message="Storing in database...",
                                         append_log="⏳ Storing vectors in Endee database...")
                count = vector_store.store_embeddings(repo_url, vectors)
                results["inserted_vectors"] = count
                task_manager.update_task(repo_url, progress=95, append_log=f"✔ Successfully stored {count} vectors.")
                
                # Metadata Updates
                task_manager.update_task(repo_url, progress=98, message="Finalizing indexing...",
                                         append_log="⏳ Updating file tracker and commit metadata...")
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
        logger.info(f"[RepoMind] Background indexing completed for {repo_url}")
        return results

    except Exception as e:
        logger.exception(f"[RepoMind] Indexing failed: {e}")
        task_manager.update_task(repo_url, status="failed", error=str(e), 
                                 message="Indexing failed.",
                                 append_log=f"❌ Error: {str(e)}")
        results["error"] = str(e)
        return results
