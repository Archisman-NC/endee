import os
import sys
import unittest
import threading
import time
from unittest.mock import patch, MagicMock

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion import task_manager
from ingestion.pipeline import run_indexing_pipeline

class TestBackgroundIndexing(unittest.TestCase):
    def test_task_manager_with_logs(self):
        """Verify task manager can store and retrieve activity logs."""
        repo = "repo_log_test"
        task_manager.init_task(repo)
        task_manager.update_task(repo, append_log="Step 1")
        task_manager.update_task(repo, append_log="Step 2")
        
        task = task_manager.get_task(repo)
        self.assertEqual(len(task["logs"]), 3)
        self.assertEqual(task["logs"][0], "⏳ Added to task queue.")
        self.assertEqual(task["logs"][1], "Step 1")
        print("Test: PASS (Task manager activity log storage verified)")

    def test_pipeline_log_reporting(self):
        """Verify the pipeline reports its steps to the activity log."""
        repo_url = "https://github.com/org/log-repo"
        
        with patch('ingestion.github_loader.clone_repo', return_value="/tmp/test"):
            with patch('ingestion.delta_detector.detect_changes', return_value={"status": "skipped"}):
                run_indexing_pipeline(repo_url)
                
                task = task_manager.get_task(repo_url)
                self.assertGreater(len(task["logs"]), 2)
                # Check for some expected logs
                self.assertTrue(any("Initializing" in log for log in task["logs"]))
                self.assertTrue(any("cloned" in log.lower() for log in task["logs"]))
                self.assertTrue(any("No changes detected" in log for log in task["logs"]))
                print("Test: PASS (Pipeline successfully reported its activity logs)")

    def test_task_queue_concurrency(self):
        """Verify that multiple tasks can be queued and processed."""
        repo1 = "https://github.com/org/repo1"
        repo2 = "https://github.com/org/repo2"
        
        with patch('ingestion.github_loader.clone_repo', return_value="/tmp/test"):
            with patch('ingestion.delta_detector.detect_changes', return_value={"status": "skipped"}):
                # Submit multiple tasks
                task_manager.submit_task(repo1)
                task_manager.submit_task(repo2)
                
                # Wait a bit for workers to pick them up
                time.sleep(1)
                
                task1 = task_manager.get_task(repo1)
                task2 = task_manager.get_task(repo2)
                
                self.assertIsNotNone(task1)
                self.assertIsNotNone(task2)
                # Success depend on how fast mock runs, but status should at least be 'running' or 'completed'
                self.assertIn(task1["status"], ["running", "completed"])
                self.assertIn(task2["status"], ["running", "completed"])
                print("Test: PASS (Multiple tasks queued and processed by workers)")

    def test_worker_safety(self):
        """Smoke test for worker stability."""
        repo_url = "https://github.com/test/worker-test"
        with patch('ingestion.github_loader.clone_repo', side_effect=Exception("worker failure")):
            task_manager.submit_task(repo_url)
            time.sleep(1)
            
        task = task_manager.get_task(repo_url)
        self.assertEqual(task["status"], "failed")
        print("Test: PASS (Worker handled indexing failure gracefully)")

if __name__ == "__main__":
    unittest.main()
