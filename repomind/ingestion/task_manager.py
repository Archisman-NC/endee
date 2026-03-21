import logging
import redis
from queue import Queue
from threading import Lock, Thread
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

import os

# Redis Connection for task mapping (Phase 5)
redis_host = os.getenv("REDIS_HOST", "localhost")
redis_port = int(os.getenv("REDIS_PORT", "6379"))

try:
    _redis_client = redis.Redis(host=redis_host, port=redis_port, db=0, decode_responses=True)
except Exception as e:
    logger.error(f"[RepoMind] Could not connect to Redis: {e}")
    _redis_client = None

# Thread-safe local task registry (for backwards compatibility/fallback)
_tasks: Dict[str, Dict[str, Any]] = {}
_task_lock = Lock()

def init_task(repo_id: str):
    """Initializes a new task state."""
    with _task_lock:
        _tasks[repo_id] = {
            "status": "pending",
            "progress": 0,
            "message": "Initializing...",
            "logs": ["⏳ Added to task queue."], 
            "error": None
        }

def update_task(repo_id: str, status: Optional[str] = None, progress: Optional[int] = None, 
                message: Optional[str] = None, error: Optional[str] = None, 
                append_log: Optional[str] = None):
    """Updates an existing task state."""
    # In Phase 5, this is called by the pipeline. 
    # If running in a thread (local), it updates _tasks.
    # If running in Celery, the pipeline ALSO triggers the celery callback.
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
    """Retrieves the current state of a task, prioritizing Celery/Redis (Phase 5)."""
    # 1. Check Redis for Celery Task ID
    if _redis_client:
        task_id = _redis_client.get(f"task_id:{repo_id}")
        if task_id:
            from celery.result import AsyncResult
            from celery_app import celery_app
            res = AsyncResult(task_id, app=celery_app)
            
            # Construct task state from Celery/Redis
            state = {
                "status": res.state.lower(),
                "progress": 0,
                "message": "",
                "logs": [],
                "error": None
            }
            
            if res.info and isinstance(res.info, dict):
                state["progress"] = res.info.get("progress", 0)
                state["message"] = res.info.get("message", "")
                state["logs"] = res.info.get("logs", []) # Full list from Phase 5
                if res.info.get("error"):
                    state["error"] = res.info.get("error")
            elif isinstance(res.info, Exception):
                state["error"] = str(res.info)
            
            if res.state == "SUCCESS":
                state["status"] = "completed"
                state["progress"] = 100
                state["message"] = "Indexing completed!"
            elif res.state == "FAILURE":
                state["status"] = "failed"
                state["error"] = str(res.result)
                
            return state

    # 2. Fallback to local _tasks dict
    with _task_lock:
        return _tasks.get(repo_id).copy() if repo_id in _tasks else None

def list_tasks() -> Dict[str, Dict[str, Any]]:
    """Returns a copy of all tasks."""
    with _task_lock:
        return {k: v.copy() for k, v in _tasks.items()}

# ── Celery Submission (Phase 5) ─────────────────────────────────────────────

def submit_task(repo_url: str):
    """Submits a new indexing task to Celery (Phase 5)."""
    repo_id = repo_url.strip()
    
    # Lazy import
    from ingestion.tasks import run_indexing_task
    
    # 1. Submit to Celery
    result = run_indexing_task.delay(repo_id)
    
    # 2. Store mapping in Redis for persistence
    if _redis_client:
        _redis_client.set(f"task_id:{repo_id}", result.id)
    
    # 3. For local session continuity
    with _task_lock:
        _tasks[repo_id] = {"status": "pending", "progress": 0, "message": "Queued in Celery...", "logs": ["⏳ Submitted to Celery."], "error": None}
    
    logger.info(f"[RepoMind] Task submitted to Celery: {result.id} for {repo_id}")
