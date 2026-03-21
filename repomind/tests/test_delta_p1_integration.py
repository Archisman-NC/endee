import os
import sys
import shutil
import json
import unittest

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.code_chunker import chunk_code_repository

class TestDeltaP1Integration(unittest.TestCase):
    def setUp(self):
        self.test_repo_id = "test_repo_id"
        self.test_repo_path = os.path.join(os.path.dirname(__file__), 'test_data_p1')
        self.test_index = ".repomind_index.json"
        
        # Create test directory and files
        os.makedirs(self.test_repo_path, exist_ok=True)
        self.file1 = "test1.py"
        self.file1_content = "def hello():\n    print('hello world')"
        with open(os.path.join(self.test_repo_path, self.file1), 'w') as f:
            f.write(self.file1_content)
            
        if os.path.exists(self.test_index):
            os.remove(self.test_index)

    def tearDown(self):
        if os.path.exists(self.test_repo_path):
            shutil.rmtree(self.test_repo_path)
        if os.path.exists(self.test_index):
            os.remove(self.test_index)

    def test_chunking_updates_index(self):
        # Run chunking with repo_id
        chunks = chunk_code_repository(self.test_repo_path, repo_id=self.test_repo_id)
        
        # Verify chunks are generated
        self.assertGreater(len(chunks), 0)
        
        # Verify index file is created
        self.assertTrue(os.path.exists(self.test_index))
        
        # Load index and check for file1
        with open(self.test_index, 'r') as f:
            index = json.load(f)
            
        self.assertIn(self.test_repo_id, index)
        self.assertIn(self.file1, index[self.test_repo_id])
        
        # Verify hash matches
        import hashlib
        expected_hash = hashlib.sha256(self.file1_content.encode('utf-8')).hexdigest()
        self.assertEqual(index[self.test_repo_id][self.file1]["hash"], expected_hash)
        
        # Verify multiple files
        file2 = "test2.py"
        file2_content = "def goodbye():\n    print('goodbye')"
        with open(os.path.join(self.test_repo_path, file2), 'w') as f:
            f.write(file2_content)
            
        # Run again
        chunk_code_repository(self.test_repo_path, repo_id=self.test_repo_id)
        
        with open(self.test_index, 'r') as f:
            updated_index = json.load(f)
            
        self.assertIn(file2, updated_index[self.test_repo_id])
        self.assertEqual(updated_index[self.test_repo_id][self.file1]["hash"], expected_hash)

if __name__ == "__main__":
    unittest.main()
