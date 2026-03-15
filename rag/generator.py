import logging
import os
from typing import List, Dict, Any
from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an expert code assistant helping developers understand codebases.
You are given relevant code snippets retrieved from a repository, followed by a user question.
Your job is to:
1. Explain clearly and concisely based on the provided code context.
2. Reference specific files and function names when relevant.
3. If the context is insufficient, say so honestly instead of guessing.

Respond in plain, readable prose. Do not fabricate code that isn't in the context."""


def _build_prompt(query: str, retrieved_chunks: List[Dict[str, Any]]) -> str:
    """Constructs the user-turn prompt from the query and retrieved code chunks."""
    context_blocks = []
    for chunk in retrieved_chunks:
        file_path = chunk.get("file_path", "unknown")
        content = chunk.get("content", "")
        context_blocks.append(f"### File: `{file_path}`\n```\n{content}\n```")

    context_section = "\n\n".join(context_blocks) if context_blocks else "No relevant code found."

    return (
        f"## Code Context\n\n{context_section}\n\n"
        f"## Question\n\n{query}"
    )


def generate_answer(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Generates a natural language explanation for a query using an LLM and retrieved code context.

    Args:
        query (str): The natural language question about the codebase.
        retrieved_chunks (List[Dict[str, Any]]): Code chunks from the retriever,
            each with 'content', 'file_path', 'chunk_id', and 'similarity'.

    Returns:
        Dict[str, Any]: A dict containing:
            - 'answer'       : LLM-generated explanation (str)
            - 'source_files' : Deduplicated list of source file paths (List[str])
            - 'query'        : The original query (str)
    """
    if not query or not query.strip():
        return {"answer": "Please provide a valid query.", "source_files": [], "query": query}

    # Collect unique source files
    source_files = list(dict.fromkeys(
        c["file_path"] for c in retrieved_chunks if c.get("file_path")
    ))

    # Build the prompt
    user_prompt = _build_prompt(query, retrieved_chunks)

    # Initialize LLM via LangChain (model configured via env var)
    model_name = os.getenv("LLM_MODEL", "gpt-4o-mini")
    provider = os.getenv("LLM_PROVIDER", "openai")

    logger.info(f"Calling LLM ({provider}/{model_name}) for query: '{query}'")

    try:
        llm = init_chat_model(model_name, model_provider=provider)
        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_prompt),
        ]
        response = llm.invoke(messages)
        answer = response.content

    except Exception as e:
        logger.error(f"LLM call failed: {e}")
        answer = f"[LLM Error] Could not generate answer: {e}"

    return {
        "answer": answer,
        "source_files": source_files,
        "query": query,
    }
