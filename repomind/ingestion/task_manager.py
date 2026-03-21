import logging
from queue import Queue
from threading import Lock, Thread
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Thread-safe task registry
_tasks: Dict[str, Dict[str, Any]] = {}
_task_lock = Lock()

# Task Queue
_task_queue: Queue = Queue()

def init_task(repo_id: str):
    """Initializes a new task state."""
    with _task_lock:
        _tasks[repo_id] = {
            "status": "pending",
            "progress": 0,
            "message": "Initializing...",
            "logs": ["⏳ Added to task queue."], # Phase 4 log update
            "error": None
        }

def update_task(repo_id: str, status: Optional[str] = None, progress: Optional[int] = None, 
                message: Optional[str] = None, error: Optional[str] = None, 
                append_log: Optional[str] = None):
    """Updates an existing task state."""
    with _task_lock:
        if repo_id not in _tasks:
            _tasks[repo_id] = {"status": "pending", "progress": 0, "message": "", "logs": [], "error": None}
            
        if status:
            _tasks[repo_id]["status"] = status
        if progress is not None:
            _tasks[repo_id]["progress"] = progress
        if message:
            _tasks[repo_id]["message"] = message
        if error:
            _tasks[repo_id]["error"] = error
        if append_log:
            _tasks[repo_id]["logs"].append(append_log)

def get_task(repo_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves the current state of a task."""
    with _task_lock:
        return _tasks.get(repo_id).copy() if repo_id in _tasks else None

def list_tasks() -> Dict[str, Dict[str, Any]]:
    """Returns a copy of all tasks."""
    with _task_lock:
        return {k: v.copy() for k, v in _tasks.items()}

# ── Worker System (Phase 4) ───────────────────────────────────────────────────

def _process_task_logic(task: Dict[str, Any]):
    """Processes a single task from the queue."""
    repo_url = task["repo_url"]
    
    # Lazy import to avoid circular dependency with pipeline.py
    from ingestion.pipeline import run_indexing_pipeline
    
    logger.info(f"[RepoMind] Worker started processing {repo_url}")
    update_task(repo_url, status="running", append_log="🚀 Processing started from queue...")
    
    run_indexing_pipeline(repo_url)
    
    # Status is handled inside run_indexing_pipeline (it sets completed or failed)
    logger.info(f"[RepoMind] Task processed for {repo_url}")

def _worker():
    """Infinite loop for processing queue items."""
    while True:
        task = _task_queue.get()
        try:
            _process_task_logic(task)
        except Exception as e:
            logger.error(f"[RepoMind] Worker thread error: {e}")
        finally:
            _task_queue.task_done()

def submit_task(repo_url: str):
    """Submits a new indexing task to the queue."""
    repo_id = repo_url.strip()
    
    # Initialize state before queuing
    init_task(repo_id)
    
    _task_queue.put({"repo_url": repo_id})
    logger.info(f"[RepoMind] Task added to queue for {repo_id}")

# Start worker threads upon import
for i in range(2):
    t = Thread(target=_worker, daemon=True, name=f"RepoMindWorker-{i}")
    t.start()
