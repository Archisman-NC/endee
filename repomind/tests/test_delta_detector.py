import os
import sys
import shutil
import unittest
import hashlib
from unittest.mock import patch

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion import delta_detector
from ingestion import file_tracker

class TestDeltaDetector(unittest.TestCase):
    def setUp(self):
        self.test_repo_id = "test_repo_delta"
        self.test_repo_path = os.path.join(os.path.dirname(__file__), 'test_repo_delta_dir')
        
        # Cleanup if exists
        if os.path.exists(self.test_repo_path):
            shutil.rmtree(self.test_repo_path)
        os.makedirs(self.test_repo_path)
        
        # Create some initial files
        self.file1 = "file1.py"
        self.file2 = "file2.py"
        with open(os.path.join(self.test_repo_path, self.file1), 'w') as f:
            f.write("print('hello')")
        with open(os.path.join(self.test_repo_path, self.file2), 'w') as f:
            f.write("print('world')")

    def tearDown(self):
        if os.path.exists(self.test_repo_path):
            shutil.rmtree(self.test_repo_path)

    def test_get_current_file_hashes(self):
        hashes = delta_detector.get_current_file_hashes(self.test_repo_path)
        self.assertEqual(len(hashes), 2)
        self.assertIn(self.file1, hashes)
        self.assertIn(self.file2, hashes)
        
        # Verify hash content
        expected_hash = hashlib.sha256("print('hello')".encode('utf-8')).hexdigest()
        self.assertEqual(hashes[self.file1], expected_hash)

    def test_detect_changes_first_run(self):
        # Mock load_index to return empty (first run)
        with patch('ingestion.delta_detector.load_index', return_value={}):
            results = delta_detector.detect_changes(self.test_repo_id, self.test_repo_path)
            
        self.assertEqual(len(results["new"]), 2)
        self.assertEqual(len(results["modified"]), 0)
        self.assertEqual(len(results["deleted"]), 0)

    def test_detect_changes_with_no_changes(self):
        # Pre-populate index
        current_hashes = delta_detector.get_current_file_hashes(self.test_repo_path)
        mock_index = {path: {"hash": h, "last_indexed": "..."} for path, h in current_hashes.items()}
        
        with patch('ingestion.delta_detector.load_index', return_value=mock_index):
            results = delta_detector.detect_changes(self.test_repo_id, self.test_repo_path)
            
        self.assertEqual(len(results["unchanged"]), 2)
        self.assertEqual(len(results["new"]), 0)

    def test_detect_changes_mixed_scenarios(self):
        # 1. Start with file1 and file2 in index
        file1_hash = hashlib.sha256("print('hello')".encode('utf-8')).hexdigest()
        file2_hash = hashlib.sha256("print('world')".encode('utf-8')).hexdigest()
        
        mock_index = {
            self.file1: {"hash": file1_hash, "last_indexed": "..."},
            self.file2: {"hash": file2_hash, "last_indexed": "..."}
        }
        
        # 2. Modify file1
        with open(os.path.join(self.test_repo_path, self.file1), 'w') as f:
            f.write("print('hello modified')")
        
        # 3. Add file3
        file3 = "file3.py"
        with open(os.path.join(self.test_repo_path, file3), 'w') as f:
            f.write("print('new file')")
            
        # 4. Delete file2
        os.remove(os.path.join(self.test_repo_path, self.file2))
        
        with patch('ingestion.delta_detector.load_index', return_value=mock_index):
            results = delta_detector.detect_changes(self.test_repo_id, self.test_repo_path)
            
        self.assertIn(self.file1, results["modified"])
        self.assertIn(file3, results["new"])
        self.assertIn(self.file2, results["deleted"])
        self.assertEqual(len(results["unchanged"]), 0)

if __name__ == "__main__":
    unittest.main()
