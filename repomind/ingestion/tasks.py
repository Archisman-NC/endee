from celery_app import celery_app
from ingestion.pipeline import run_indexing_pipeline
import logging

logger = logging.getLogger(__name__)

@celery_app.task(bind=True, max_retries=3)
def run_indexing_task(self, repo_url: str):
    """
    Celery task to run the indexing pipeline.
    """
    logger.info(f"[Celery] Starting indexing task for {repo_url}")
    
    # Store logs in a list and pass the full list to update_state
    task_logs = ["⏳ Submitted to Celery."]
    
    def celery_progress_callback(progress, message, log=None, error=None):
        if log:
            task_logs.append(log)
        
        meta = {
            "progress": progress,
            "message": message,
            "logs": task_logs, # Pass full history
            "error": error
        }
        # Update Celery state
        self.update_state(state="PROGRESS", meta=meta)
        
    try:
        results = run_indexing_pipeline(repo_url, progress_callback=celery_progress_callback)
        return results
    except Exception as e:
        logger.error(f"[Celery] Task failed for {repo_url}: {e}")
        raise self.retry(exc=e, countdown=10)
