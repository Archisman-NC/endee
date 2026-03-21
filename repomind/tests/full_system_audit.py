import os
import sys
import shutil
import unittest
import time
import subprocess
from unittest.mock import patch, MagicMock

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion import file_tracker, delta_detector, git_utils, code_chunker
from rag import vector_store

class FullSystemAudit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo_id = "audit_repo"
        cls.repo_path = os.path.join(os.path.dirname(__file__), 'audit_repo_dir')
        cls.index_file = ".repomind_index.json"
        
    def setUp(self):
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)
        os.makedirs(self.repo_path)
        
        if os.path.exists(self.index_file):
            os.remove(self.index_file)
            
        # Initialize as git repo
        subprocess.run(["git", "init"], cwd=self.repo_path, capture_output=True)
        subprocess.run(["git", "config", "user.email", "audit@example.com"], cwd=self.repo_path)
        subprocess.run(["git", "config", "user.name", "Auditor"], cwd=self.repo_path)
        
        # Initial file
        self.file1 = "main.py"
        with open(os.path.join(self.repo_path, self.file1), 'w') as f:
            f.write("print('initial')")
        subprocess.run(["git", "add", "."], cwd=self.repo_path)
        subprocess.run(["git", "commit", "-m", "initial"], cwd=self.repo_path)

    def tearDown(self):
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)
        if os.path.exists(self.index_file):
            os.remove(self.index_file)

    def test_01_initial_indexing(self):
        """Test 1: Initial Indexing"""
        changes = delta_detector.detect_changes(self.repo_id, self.repo_path)
        self.assertIn(self.file1, changes["new"])
        self.assertEqual(changes["status"], "ok")
        print("\nTest 1: PASS (Initial Indexing detected NEW files)")

    def test_02_idempotency(self):
        """Test 2: No Changes (Idempotency)"""
        # First "index" simulation: update tracker
        current_commit = git_utils.get_latest_commit_hash(self.repo_path)
        file_tracker.update_file_record(self.repo_id, self.file1, "hash1")
        file_tracker.update_repo_metadata(self.repo_id, {"last_commit": current_commit})
        
        # Second run
        changes = delta_detector.detect_changes(self.repo_id, self.repo_path)
        self.assertEqual(changes["status"], "skipped")
        print("Test 2: PASS (Idempotency - System skipped indexing)")

    def test_03_modify_one_file(self):
        """Test 3: Modify One File"""
        # Index initial
        file_tracker.update_file_record(self.repo_id, self.file1, file_tracker.compute_file_hash("print('initial')"))
        file_tracker.update_repo_metadata(self.repo_id, {"last_commit": git_utils.get_latest_commit_hash(self.repo_path)})
        
        # Modify
        with open(os.path.join(self.repo_path, self.file1), 'w') as f:
            f.write("print('modified')")
        subprocess.run(["git", "add", "."], cwd=self.repo_path)
        subprocess.run(["git", "commit", "-m", "modify"], cwd=self.repo_path)
        
        changes = delta_detector.detect_changes(self.repo_id, self.repo_path)
        self.assertIn(self.file1, changes["modified"])
        self.assertEqual(len(changes["new"]), 0)
        print("Test 3: PASS (Modified file detected accurately)")

    def test_04_add_new_file(self):
        """Test 4: Add New File"""
        file_tracker.update_file_record(self.repo_id, self.file1, file_tracker.compute_file_hash("print('initial')"))
        file_tracker.update_repo_metadata(self.repo_id, {"last_commit": git_utils.get_latest_commit_hash(self.repo_path)})
        
        new_file = "utils.py"
        with open(os.path.join(self.repo_path, new_file), 'w') as f:
            f.write("def foo(): pass")
        subprocess.run(["git", "add", "."], cwd=self.repo_path)
        subprocess.run(["git", "commit", "-m", "add file"], cwd=self.repo_path)
        
        changes = delta_detector.detect_changes(self.repo_id, self.repo_path)
        self.assertIn(new_file, changes["new"])
        print("Test 4: PASS (New file detected accurately)")

    def test_05_delete_file(self):
        """Test 5: Delete File"""
        file_tracker.update_file_record(self.repo_id, self.file1, file_tracker.compute_file_hash("print('initial')"))
        file_tracker.update_repo_metadata(self.repo_id, {"last_commit": git_utils.get_latest_commit_hash(self.repo_path)})
        
        os.remove(os.path.join(self.repo_path, self.file1))
        subprocess.run(["git", "add", "."], cwd=self.repo_path)
        subprocess.run(["git", "commit", "-m", "delete file"], cwd=self.repo_path)
        
        changes = delta_detector.detect_changes(self.repo_id, self.repo_path)
        self.assertIn(self.file1, changes["deleted"])
        print("Test 5: PASS (Deleted file detected accurately)")

    def test_08_git_optimization(self):
        """Test 8: Git-Based Optimization"""
        file_tracker.update_file_record(self.repo_id, self.file1, "hash1")
        file_tracker.update_repo_metadata(self.repo_id, {"last_commit": git_utils.get_latest_commit_hash(self.repo_path)})
        
        # Add a file but don't commit it? Wait, git diff needs a commit or index.
        with open(os.path.join(self.repo_path, "new.py"), 'w') as f: f.write("new")
        subprocess.run(["git", "add", "."], cwd=self.repo_path)
        subprocess.run(["git", "commit", "-m", "git opt"], cwd=self.repo_path)
        
        with patch('ingestion.git_utils.get_changed_files') as mock_git:
            mock_git.return_value = ["new.py"]
            changes = delta_detector.detect_changes(self.repo_id, self.repo_path)
            mock_git.assert_called()
            self.assertIn("new.py", changes["new"])
        print("Test 8: PASS (Git optimization used for candidate filtering)")

    def test_06_metadata_integrity(self):
        """Test 6: Metadata Integrity"""
        # Mock vectors
        vectors = [
            {"embedding": [0.1]*384, "file_path": "main.py", "content": "hi", "chunk_index": 0, "total_chunks": 1}
        ]
        
        with patch('rag.vector_store._get_index') as mock_get_index:
            mock_idx = MagicMock()
            mock_get_index.return_value = mock_idx
            
            vector_store.store_embeddings(self.repo_id, vectors)
            
            # Check the upsert call
            upsert_batches = mock_idx.upsert.call_args[0][0]
            meta = upsert_batches[0]["meta"]
            
            self.assertEqual(meta["repo_id"], self.repo_id)
            self.assertEqual(meta["file_path"], "main.py")
            self.assertIn("chunk_id", meta)
            self.assertEqual(meta["chunk_index"], 0)
            self.assertEqual(meta["total_chunks"], 1)
        print("Test 6: PASS (All critical metadata fields present in vector payload)")

    def test_07_modified_file_consistency(self):
        """Test 7: Modified File Consistency"""
        # Mock the flow: modify -> delete old -> insert new
        with patch('rag.vector_store._get_index') as mock_get_index:
            mock_idx = MagicMock()
            mock_get_index.return_value = mock_idx
            # Mock query to return some IDs
            mock_idx.query.return_value = [{"id": "chunk1", "meta": {"file_path": self.file1}}]
            
            # Simulate a modification cleanup
            vector_store.delete_vectors_by_file(self.repo_id, self.file1)
            mock_idx.delete.assert_called_with(ids=["chunk1"])
        print("Test 7: PASS (Old vectors explicitly purged before re-indexing)")

    def test_09_commit_hash_tracking(self):
        """Test 9: Commit Hash Tracking"""
        commit = git_utils.get_latest_commit_hash(self.repo_path)
        file_tracker.update_repo_metadata(self.repo_id, {"last_commit": commit})
        
        meta = file_tracker.get_repo_metadata(self.repo_id)
        self.assertEqual(meta.get("last_commit"), commit)
        print("Test 9: PASS (Commit hash correctly persisted in index JSON)")

    def test_10_fallback_mode(self):
        """Test 10: Fallback Mode"""
        # Remove .git
        shutil.rmtree(os.path.join(self.repo_path, ".git"))
        
        changes = delta_detector.detect_changes(self.repo_id, self.repo_path)
        self.assertIn(self.file1, changes["new"]) # First run in non-git
        self.assertEqual(changes["status"], "ok") 
        print("Test 10: PASS (Fallback to hash-based for non-git folder)")

if __name__ == "__main__":
    unittest.main()
