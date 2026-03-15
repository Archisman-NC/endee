import os
import sys
import tempfile
import logging

import streamlit as st

# Ensure project root is on path regardless of where streamlit is invoked from
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ingestion.github_loader import clone_repo
from ingestion.code_chunker import chunk_code_repository
from rag.embeddings import generate_embeddings
from rag.vector_store import store_embeddings
from rag.retriever import retrieve_relevant_chunks
from rag.generator import generate_answer

logging.basicConfig(level=logging.WARNING)

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RepoMind — Chat with your Codebase",
    page_icon="🧠",
    layout="wide",
)

# ── Custom CSS ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    /* Sidebar */
    section[data-testid="stSidebar"] {
        background: #0f1117;
        border-right: 1px solid #1e2130;
    }

    /* Top banner */
    .banner {
        background: linear-gradient(135deg, #1a1f2e 0%, #0f1117 100%);
        border: 1px solid #2a3050;
        border-radius: 12px;
        padding: 1.5rem 2rem;
        margin-bottom: 1.5rem;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    .banner h1 { margin: 0; font-size: 1.6rem; font-weight: 700; color: #ffffff; }
    .banner p  { margin: 0; font-size: 0.9rem; color: #8892b0; }

    /* Chat bubbles */
    .msg-user {
        background: #1e2130;
        border-left: 3px solid #5b7cfa;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.8rem;
        color: #cdd6f4;
    }
    .msg-assistant {
        background: #141824;
        border-left: 3px solid #50fa7b;
        border-radius: 8px;
        padding: 0.8rem 1rem;
        margin-bottom: 0.8rem;
        color: #cdd6f4;
    }
    .source-tag {
        display: inline-block;
        background: #1e2130;
        border: 1px solid #2a3050;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.75rem;
        color: #8892b0;
        margin: 2px;
        font-family: monospace;
    }
    .status-ok   { color: #50fa7b; font-weight: 600; }
    .status-err  { color: #ff5555; font-weight: 600; }

    /* Hide Streamlit branding */
    #MainMenu, footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ── Session state defaults ────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []
if "indexed_repo" not in st.session_state:
    st.session_state.indexed_repo = None
if "chunk_count" not in st.session_state:
    st.session_state.chunk_count = 0

# ── Sidebar — Repository Indexer ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗂️ Repository")
    st.caption("Paste a public GitHub URL to index a codebase.")

    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/owner/repo",
        label_visibility="collapsed",
    )

    index_btn = st.button("⚡ Index Repository", use_container_width=True, type="primary")

    if index_btn:
        if not repo_url.strip():
            st.error("Please enter a repository URL.")
        else:
            with st.spinner("Cloning repository…"):
                try:
                    dest = os.path.join(tempfile.gettempdir(), "repomind_repos",
                                        repo_url.rstrip("/").split("/")[-1])
                    repo_path = clone_repo(repo_url.strip(), dest)
                    st.session_state.indexed_repo = repo_url.strip()
                except Exception as e:
                    st.error(f"Clone failed: {e}")
                    st.stop()

            with st.spinner("Chunking code files…"):
                chunks = chunk_code_repository(repo_path)

            with st.spinner(f"Generating embeddings for {len(chunks)} chunks…"):
                vectors = generate_embeddings(chunks)

            with st.spinner("Storing vectors in Endee…"):
                try:
                    count = store_embeddings(vectors)
                    st.session_state.chunk_count = count
                    st.success(f"✅ Indexed **{count}** chunks successfully!")
                    # Reset chat on new repo
                    st.session_state.messages = []
                except Exception as e:
                    st.error(f"Vector store error: {e}")

    st.divider()

    if st.session_state.indexed_repo:
        st.markdown(f"**Active repo:**")
        st.code(st.session_state.indexed_repo.split("/")[-1], language=None)
        st.caption(f"{st.session_state.chunk_count:,} chunks indexed")
    else:
        st.caption("No repository indexed yet.")

    if st.button("🗑️ Clear Chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

# ── Main — Chat Interface ─────────────────────────────────────────────────────
st.markdown("""
<div class="banner">
  <div>
    <h1>🧠 RepoMind</h1>
    <p>Ask questions about any GitHub repository. Powered by semantic search + LLM.</p>
  </div>
</div>
""", unsafe_allow_html=True)

# Render chat history
for msg in st.session_state.messages:
    if msg["role"] == "user":
        st.markdown(f'<div class="msg-user">💬 {msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="msg-assistant">🤖 {msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("source_files"):
            sources_html = " ".join(
                f'<span class="source-tag">📄 {f}</span>' for f in msg["source_files"]
            )
            st.markdown(f"**Sources:** {sources_html}", unsafe_allow_html=True)

# Chat input
if not st.session_state.indexed_repo:
    st.info("👈 Index a repository from the sidebar to start chatting.")
else:
    query = st.chat_input("Ask anything about this codebase…")
    if query:
        # Store user message
        st.session_state.messages.append({"role": "user", "content": query})
        st.markdown(f'<div class="msg-user">💬 {query}</div>', unsafe_allow_html=True)

        with st.spinner("Searching codebase…"):
            chunks = retrieve_relevant_chunks(query, top_k=5)

        with st.spinner("Generating answer…"):
            result = generate_answer(query, chunks)

        # Store and display assistant message
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["answer"],
            "source_files": result["source_files"],
        })

        st.markdown(f'<div class="msg-assistant">🤖 {result["answer"]}</div>', unsafe_allow_html=True)

        if result["source_files"]:
            sources_html = " ".join(
                f'<span class="source-tag">📄 {f}</span>' for f in result["source_files"]
            )
            st.markdown(f"**Sources:** {sources_html}", unsafe_allow_html=True)

        st.rerun()
