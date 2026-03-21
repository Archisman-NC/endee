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

# ── Configuration Helpers ────────────────────────────────────────────────────
def get_config(key, default=None):
    """Retrieve configuration from st.secrets or environment variables."""
    # 1. Try Streamlit Secrets (for Cloud)
    if key in st.secrets:
        return st.secrets[key]
    # 2. Try Environment Variables (for Local/Docker)
    return os.getenv(key, default)

GROQ_API_KEY = get_config("GROQ_API_KEY")
OPENAI_API_KEY = get_config("OPENAI_API_KEY")
ENDEE_BASE_URL = get_config("ENDEE_BASE_URL", "http://localhost:8080/api/v1")
LLM_PROVIDER = get_config("LLM_PROVIDER", "groq")
LLM_MODEL = get_config("LLM_MODEL", "llama-3.3-70b-versatile")
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
if "is_streaming" not in st.session_state:
    st.session_state.is_streaming = False

# ── Sidebar — Repository Indexer ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🗂️ Repository")
    st.caption("Paste a public GitHub URL to index a codebase.")

    repo_url = st.text_input(
        "GitHub Repository URL",
        placeholder="https://github.com/owner/repo",
        label_visibility="collapsed",
    )

    # Check for active background task
    from ingestion import task_manager
    active_task = None
    if st.session_state.indexed_repo:
        active_task = task_manager.get_task(st.session_state.indexed_repo)
    
    is_running = active_task and active_task["status"] == "running"

    index_btn = st.button(
        "⚡ Index Repository", 
        use_container_width=True, 
        type="primary",
        disabled=is_running
    )

    if index_btn:
        if not repo_url.strip():
            st.error("Please enter a repository URL.")
        else:
            from ingestion import task_manager
            st.session_state.indexed_repo = repo_url.strip()
            
            # Submit to background task queue (Phase 4)
            task_manager.submit_task(st.session_state.indexed_repo)
            st.rerun()

    st.divider()

    if st.session_state.indexed_repo:
        st.markdown(f"**Active repo:**")
        st.code(st.session_state.indexed_repo.split("/")[-1], language=None)
        
        # Display background task dashboard
        task = task_manager.get_task(st.session_state.indexed_repo)
        if task:
            # 1. Status Badge
            if task["status"] == "running":
                st.info("🔵 Indexing in progress...")
            elif task["status"] == "completed":
                st.success("✅ Indexing completed!")
            elif task["status"] == "failed":
                st.error("❌ Indexing failed")
            
            # 2. Progress Bar
            st.progress(task["progress"] / 100.0)
            
            # 3. Current Step & Percentage
            col_msg, col_pct = st.columns([3, 1])
            with col_msg:
                st.caption(f"Step: {task['message']}")
            with col_pct:
                st.caption(f"{task['progress']}%")
            
            # 4. Activity Log (Recent steps)
            if task["logs"]:
                with st.expander("📄 Activity Log", expanded=task["status"] == "running"):
                    for log_msg in reversed(task["logs"][-10:]): # Show last 10 logs
                        st.markdown(f"<p style='font-size: 0.8rem; margin: 0;'>{log_msg}</p>", unsafe_allow_html=True)
            
            if task["error"]:
                st.error(f"Error Details: {task['error']}")
            
            # 5. Auto-refresh if running
            if task["status"] == "running":
                import time
                time.sleep(1)
                st.rerun()
        
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
    # Phase 5: Disable input while streaming
    query = st.chat_input(
        "Ask anything about this codebase…", 
        disabled=st.session_state.is_streaming
    )
    
    if query:
        # 1. Update state and prevent overlaps
        st.session_state.is_streaming = True
        st.session_state.messages.append({"role": "user", "content": query})
        st.rerun()

# Processing the latest user message if streaming was just triggered
if st.session_state.get("is_streaming") and st.session_state.messages:
    last_msg = st.session_state.messages[-1]
    if last_msg["role"] == "user":
        query = last_msg["content"]
        
        try:
            with st.spinner("Searching codebase…"):
                chunks = retrieve_relevant_chunks(query, top_k=5)

            # 2. Create placeholder for streaming response
            assistant_placeholder = st.empty()
            
            # 3. Generate answer with streaming (pass resolved config)
            api_key = GROQ_API_KEY if LLM_PROVIDER == "groq" else OPENAI_API_KEY
            
            result = generate_answer(
                query, 
                chunks, 
                streaming_placeholder=assistant_placeholder,
                api_key=api_key,
                provider=LLM_PROVIDER,
                model_name=LLM_MODEL
            )

            # 4. Store final assistant message in history
            st.session_state.messages.append({
                "role": "assistant",
                "content": result["answer"],
                "source_files": result["source_files"],
            })
        except Exception as e:
            st.error(f"⚠️ Error: {str(e)}")
        finally:
            st.session_state.is_streaming = False
            st.rerun()
