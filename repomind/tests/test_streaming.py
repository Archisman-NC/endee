import sys
import os

# Add the project root to the sys.path so we can import 'rag' and 'ingestion'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from rag import generator
import logging

# Configure basic logging to see the logger.info calls
logging.basicConfig(level=logging.INFO)

def test_streaming():
    print("--- Starting Streaming Verification ---")
    
    query = "What is the capital of France?"
    # Mock retrieved chunks
    retrieved_chunks = [
        {"file_path": "geography.txt", "content": "France is a country in Europe. Its capital is Paris."}
    ]
    
    print(f"Query: {query}")
    
    result = generator.generate_answer(query, retrieved_chunks)
    
    print("\n--- Verification Results ---")
    print(f"Answer: {result['answer']}")
    print(f"Source Files: {result['source_files']}")
    
    # The output should show:
    # [RepoMind] Streaming started...
    # [RepoMind] Tokens received: X
    # [RepoMind] Streaming completed.
    
    if "Paris" in result['answer']:
        print("\n✅ SUCCESS: LLM responded correctly.")
    else:
        print("\n❌ FAILURE: LLM response incomplete or incorrect.")

if __name__ == "__main__":
    test_streaming()
