import os
import sys
import shutil
import unittest
from unittest.mock import patch, MagicMock

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion import code_chunker, file_tracker, delta_detector
from rag import vector_store

class TestPhase3Delta(unittest.TestCase):
    def setUp(self):
        self.repo_id = "test_delta_p3"
        self.repo_path = os.path.join(os.path.dirname(__file__), 'test_repo_p3')
        self.index_file = ".repomind_index.json"
        
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)
        os.makedirs(self.repo_path)
        
        if os.path.exists(self.index_file):
            os.remove(self.index_file)
            
        # Create initial file
        self.file1 = "main.py"
        with open(os.path.join(self.repo_path, self.file1), 'w') as f:
            f.write("print('hello')")

    def tearDown(self):
        if os.path.exists(self.repo_path):
            shutil.rmtree(self.repo_path)
        if os.path.exists(self.index_file):
            os.remove(self.index_file)

    def test_selective_chunking(self):
        # 1. Create 2 files
        file2 = "utils.py"
        with open(os.path.join(self.repo_path, file2), 'w') as f:
            f.write("def add(a, b): return a + b")
            
        # 2. Chunk only file1
        chunks = code_chunker.chunk_code_repository(self.repo_path, include_files=[self.file1])
        
        # 3. Verify
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["file_path"], self.file1)
        
    def test_record_removal(self):
        # 1. Add record
        file_tracker.update_file_record(self.repo_id, self.file1, "hash123")
        self.assertIn(self.file1, file_tracker.load_index(self.repo_id))
        
        # 2. Remove record
        file_tracker.remove_file_record(self.repo_id, self.file1)
        self.assertNotIn(self.file1, file_tracker.load_index(self.repo_id))

    @patch('rag.vector_store._get_index')
    def test_delete_vectors_by_file(self, mock_get_index):
        # Setup mock index
        mock_idx = MagicMock()
        mock_get_index.return_value = mock_idx
        
        # Mock query results
        mock_idx.query.return_value = [
            {"id": "chunk1", "meta": {"file_path": self.file1}},
            {"id": "chunk2", "meta": {"file_path": "other.py"}}
        ]
        
        # Call delete
        count = vector_store.delete_vectors_by_file(self.repo_id, self.file1)
        
        # Verify
        self.assertEqual(count, 1)
        mock_idx.delete.assert_called_once_with(ids=["chunk1"])

if __name__ == "__main__":
    unittest.main()
