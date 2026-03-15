import os
import uuid
import logging
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter, Language

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    '.py': Language.PYTHON,
    '.js': Language.JS,
    '.ts': Language.TS,
    '.java': Language.JAVA,
    '.cpp': Language.CPP,
    '.c': Language.CPP,
    '.h': Language.CPP,
    '.hpp': Language.CPP
}

def get_text_splitter_for_ext(ext: str, chunk_size: int = 400, chunk_overlap: int = 50) -> RecursiveCharacterTextSplitter:
    """Gets the appropriate LangChain text splitter for the given file extension."""
    lang = SUPPORTED_EXTENSIONS.get(ext)
    if lang:
        return RecursiveCharacterTextSplitter.from_language(
            language=lang,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
        )
    # Default fallback
    return RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

def chunk_code_repository(repo_path: str, chunk_size: int = 400, chunk_overlap: int = 50) -> List[Dict[str, Any]]:
    """
    Reads all supported code files from a directory and splits them into chunks.
    
    Args:
        repo_path (str): The root directory to scan for code files.
        chunk_size (int): Approximate target size per chunk.
        chunk_overlap (int): Number of characters to overlap between chunks.
        
    Returns:
        List[Dict[str, Any]]: A list of chunk dictionaries containing content and metadata.
    """
    chunks = []
    
    if not os.path.exists(repo_path) or not os.path.isdir(repo_path):
        logger.error(f"Invalid repository path: {repo_path}")
        return chunks
        
    for root, _, files in os.walk(repo_path):
        # Skip common hidden/build directories
        if any(part.startswith('.') for part in root.split(os.sep)) or 'node_modules' in root or '__pycache__' in root:
            continue
            
        for file in files:
            _, ext = os.path.splitext(file)
            if ext.lower() not in SUPPORTED_EXTENSIONS:
                continue
                
            file_path = os.path.join(root, file)
            # Make path relative to repo root for cleaner metadata
            rel_path = os.path.relpath(file_path, repo_path)
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    
                if not content.strip():
                    continue
                    
                splitter = get_text_splitter_for_ext(ext.lower(), chunk_size, chunk_overlap)
                file_chunks = splitter.create_documents([content])
                
                for doc in file_chunks:
                    chunks.append({
                        "content": doc.page_content,
                        "file_path": rel_path,
                        "chunk_id": str(uuid.uuid4())
                    })
                    
            except UnicodeDecodeError:
                logger.warning(f"Skipping file due to encoding issues: {file_path}")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                
    logger.info(f"Generated {len(chunks)} chunks from {repo_path}")
    return chunks
