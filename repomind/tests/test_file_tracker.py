import os
import sys
import json
import unittest
from datetime import datetime

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion import file_tracker

class TestFileTracker(unittest.TestCase):
    def setUp(self):
        self.repo_id = "https://github.com/test/repo"
        self.test_index = ".repomind_index.json"
        if os.path.exists(self.test_index):
            os.remove(self.test_index)

    def tearDown(self):
        if os.path.exists(self.test_index):
            os.remove(self.test_index)

    def test_compute_file_hash(self):
        content = "hello world"
        expected_hash = "b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9"
        self.assertEqual(file_tracker.compute_file_hash(content), expected_hash)

    def test_save_and_load_index(self):
        data = {"file1.py": {"hash": "abc", "last_indexed": "2023-01-01"}}
        file_tracker.save_index(self.repo_id, data)
        
        loaded_data = file_tracker.load_index(self.repo_id)
        self.assertEqual(loaded_data, data)

    def test_update_file_record(self):
        file_path = "src/main.py"
        file_hash = "def456"
        file_tracker.update_file_record(self.repo_id, file_path, file_hash)
        
        loaded_data = file_tracker.load_index(self.repo_id)
        self.assertIn(file_path, loaded_data)
        self.assertEqual(loaded_data[file_path]["hash"], file_hash)
        # Check if timestamp is present
        self.assertTrue("last_indexed" in loaded_data[file_path])
        
        # Verify it can handle another update
        new_hash = "ghi789"
        file_tracker.update_file_record(self.repo_id, file_path, new_hash)
        updated_data = file_tracker.load_index(self.repo_id)
        self.assertEqual(updated_data[file_path]["hash"], new_hash)

if __name__ == "__main__":
    unittest.main()
