import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add the project root to the sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag import vector_mapper, vector_store
from ingestion import code_chunker

class TestVectorMapping(unittest.TestCase):
    def test_deterministic_id(self):
        file_path = "src/main.py"
        idx = 2
        id1 = vector_mapper.generate_chunk_id(file_path, idx)
        id2 = vector_mapper.generate_chunk_id(file_path, idx)
        
        self.assertEqual(id1, id2)
        self.assertEqual(id1, "src/main.py::chunk_2")

    def test_metadata_structure(self):
        meta = vector_mapper.generate_chunk_metadata(
            repo_id="repo123",
            file_path="app.py",
            chunk_index=0,
            total_chunks=1,
            content="print('hi')"
        )
        
        self.assertEqual(meta["repo_id"], "repo123")
        self.assertEqual(meta["chunk_index"], 0)
        self.assertEqual(meta["total_chunks"], 1)
        self.assertEqual(meta["chunk_id"], "app.py::chunk_0")

    def test_chunk_context_in_chunker(self):
        # Mock a small file processing
        with patch('builtins.open', unittest.mock.mock_open(read_data="line1\nline2\nline3")):
            with patch('os.path.exists', return_value=True):
                with patch('os.path.isdir', return_value=True):
                    with patch('os.walk', return_value=[('/root', [], ['test.py'])]):
                        # Force chunking with a small size to get multiple chunks
                        chunks = code_chunker.chunk_code_repository('/root', chunk_size=5, chunk_overlap=0)
                        
        if chunks:
            self.assertIn("chunk_index", chunks[0])
            self.assertIn("total_chunks", chunks[0])
            self.assertEqual(chunks[0]["total_chunks"], len(chunks))
            for i, c in enumerate(chunks):
                self.assertEqual(c["chunk_index"], i)

    @patch('rag.vector_store._get_index')
    def test_reindex_cleanup(self, mock_get_index):
        # Verify that if we re-index a file that previously had 3 chunks but now has 2,
        # the 3rd old chunk is correctly cleaned up by the app logic calling delete_vectors_by_file.
        # This test specifically verifies the vector_store helper.
        
        mock_idx = MagicMock()
        mock_get_index.return_value = mock_idx
        
        # Scenario: File had 3 chunks. We delete BEFORE re-inserting.
        file_path = "utils.py"
        repo_id = "my_repo"
        
        # 1. Mock the query returning 3 old chunks
        mock_idx.query.return_value = [
            {"id": f"{file_path}::chunk_0", "meta": {"file_path": file_path}},
            {"id": f"{file_path}::chunk_1", "meta": {"file_path": file_path}},
            {"id": f"{file_path}::chunk_2", "meta": {"file_path": file_path}}
        ]
        
        # 2. Call delete logic
        vector_store.delete_vectors_by_file(repo_id, file_path)
        
        # 3. Verify delete was called with all 3 IDs
        mock_idx.delete.assert_called_once()
        ids_passed = mock_idx.delete.call_args[1]["ids"]
        self.assertEqual(len(ids_passed), 3)
        self.assertIn(f"{file_path}::chunk_2", ids_passed)

if __name__ == "__main__":
    unittest.main()
