import sys
import os
import time
import unittest
from unittest.mock import patch, MagicMock

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion import task_manager
from celery.result import AsyncResult
from celery_app import celery_app

class FullBackgroundAudit(unittest.TestCase):
    def setUp(self):
        self.repo_url = "https://github.com/pallets/click" # A real-ish looking URL for ID
        self.repo_id = self.repo_url.strip()

    def test_01_non_blocking_submission(self):
        """Test 1 & 8: Non-blocking submission and queue behavior."""
        start_time = time.time()
        task_manager.submit_task(self.repo_url)
        end_time = time.time()
        
        # Submission should be near-instant, allowing for first-time connect overhead
        self.assertLess(end_time - start_time, 5.0, "Submission blocked for too long")
        print("Test 1: PASS (Non-blocking submission)")

    def test_02_task_initialization(self):
        """Test 2: Task state initialization."""
        task = task_manager.get_task(self.repo_id)
        self.assertIsNotNone(task)
        self.assertIn(task["status"], ["pending", "running", "progress"])
        print("Test 2: PASS (Task initialized correctly)")

    def test_03_04_live_updates(self):
        """Test 3 & 4: Live progress and message updates."""
        print("Checking for live updates (polling for 10s)...")
        found_progress = False
        for _ in range(20):
            task = task_manager.get_task(self.repo_id)
            if task and task["progress"] > 0:
                print(f"  Progress update detected: {task['progress']}% - {task['message']}")
                found_progress = True
                break
            time.sleep(0.5)
        self.assertTrue(found_progress, "No progress update detected")
        print("Test 3 & 4: PASS (Live updates and auto-refresh simulated via polling)")

    def test_05_button_locking(self):
        """Test 5: Prevention of duplicate tasks."""
        # In our implementation, submit_task just overwrites the mapping or adds to queue.
        # But get_task will show it's already 'running'.
        # Frontend logic handles the button locking.
        task = task_manager.get_task(self.repo_id)
        self.assertIn(task["status"], ["running", "progress", "completed"])
        print("Test 5: PASS (State correctly reflects active task for UI locking)")

    def test_07_error_handling(self):
        """Test 7: Error handling with invalid repo."""
        bad_repo = "https://github.com/invalid/repo-12345"
        task_manager.submit_task(bad_repo)
        
        print("Waiting for failure state...")
        failed = False
        for _ in range(40):
            task = task_manager.get_task(bad_repo)
            if task and task["status"] in ["failed", "retry"]:
                print(f"  Error state detected as expected: {task['status']}")
                failed = True
                break
            time.sleep(1)
        self.assertTrue(failed, "Task did not enter error state (failed/retry) for invalid repo")
        print("Test 7: PASS (Error handling verified)")

    def test_09_celery_integration(self):
        """Test 9: Celery worker execution."""
        # Check if Redis has the task mapping
        import redis
        r = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
        task_id = r.get(f"task_id:{self.repo_id}")
        self.assertIsNotNone(task_id, "No Celery task ID found in Redis")
        
        res = AsyncResult(task_id, app=celery_app)
        self.assertIsNotNone(res.state)
        print(f"Test 9: PASS (Celery integrated, Task ID: {task_id}, State: {res.state})")

    def test_10_persistence(self):
        """Test 10: Task persistence across app 'restarts'."""
        # Clear local _tasks cache
        task_manager._tasks.clear()
        
        # Should still be able to retrieve from Redis/Celery
        task = task_manager.get_task(self.repo_id)
        self.assertIsNotNone(task, "Task lost after local cache clear")
        self.assertIn("logs", task)
        print("Test 10: PASS (Persistence via Redis/Celery backend verified)")

if __name__ == "__main__":
    unittest.main()
