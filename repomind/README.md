<p align="center">
  <img src="https://img.shields.io/badge/RepoMind-AI_Code_Assistant-5b7cfa?style=for-the-badge&logo=github" alt="RepoMind">
</p>

<p align="center">
  <b>Chat with any GitHub repository using semantic search and LLMs.</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Streamlit-FF4B4B?style=flat-square&logo=streamlit&logoColor=white" alt="Streamlit">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/Endee-Vector_DB-5b7cfa?style=flat-square" alt="Endee">
  <img src="https://img.shields.io/badge/License-Apache_2.0-green?style=flat-square" alt="License">
</p>

---

## Project Overview

**RepoMind** is an AI-powered code assistant that lets you ask natural language questions about any GitHub repository and get accurate, context-aware answers grounded in the actual source code.

Point RepoMind at any public GitHub repo, and it will:

1. Clone and ingest the codebase
2. Split it into semantic code chunks
3. Store vector embeddings in **Endee** — a high-performance open-source vector database
4. Accept natural language questions through a clean chat UI
5. Retrieve the most relevant code snippets and generate clear explanations via an LLM

Whether you're onboarding to a new codebase, auditing open-source code, or building a copilot for your team, RepoMind makes codebases conversational.

---

## Problem Statement

Navigating a large or unfamiliar codebase is time-consuming and frustrating. Developers typically spend significant time:

- Reading through files manually looking for where a feature is implemented
- Tracing call stacks across multiple modules to understand data flow
- Searching for undocumented patterns and conventions
- Onboarding to new projects or open-source libraries

Traditional keyword search (`grep`, IDE search) only finds exact matches. It can't answer questions like:
> *"How is authentication handled?"* or *"Where does the routing logic live?"*

**RepoMind solves this** by applying semantic search over your codebase — understanding the *meaning* of your question, not just the words — and generating a grounded, cited answer using an LLM.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface (Streamlit)               │
│              GitHub URL input  ·  Chat interface             │
└─────────────────────────┬───────────────────────────────────┘
                          │
            ┌─────────────▼─────────────┐
            │      Ingestion Pipeline    │
            │  GitPython → code_chunker  │
            │  (splits by language rules)│
            └─────────────┬─────────────┘
                          │
            ┌─────────────▼─────────────┐
            │    Embedding Generation    │
            │  sentence-transformers     │
            │  all-MiniLM-L6-v2 (384-d) │
            └─────────────┬─────────────┘
                          │
            ┌─────────────▼─────────────┐
            │   Endee Vector Database    │
            │  Cosine similarity · INT8  │
            │  Metadata: file, chunk_id  │
            └─────────────┬─────────────┘
                          │
            ┌─────────────▼─────────────┐
            │    Semantic Retrieval      │
            │  Query → embed → top-K     │
            └─────────────┬─────────────┘
                          │
            ┌─────────────▼─────────────┐
            │     LLM Answer Generation  │
            │  LangChain + OpenAI/other  │
            │  Prompt with code context  │
            └─────────────┬─────────────┘
                          │
            ┌─────────────▼─────────────┐
            │         Chat Response      │
            │   Answer + Source Files    │
            └───────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **Ingestion** | [GitPython](https://gitpython.readthedocs.io/) | Clone GitHub repositories |
| **Chunking** | [LangChain Text Splitters](https://python.langchain.com/docs/modules/data_connection/document_transformers/) | Language-aware code splitting |
| **Embeddings** | [sentence-transformers](https://www.sbert.net/) `all-MiniLM-L6-v2` | 384-dimensional dense vectors |
| **Vector DB** | [Endee](https://endee.io/) | High-performance vector storage & retrieval |
| **LLM** | [LangChain](https://langchain.com/) + OpenAI / any provider | Grounded answer generation |
| **Backend** | [FastAPI](https://fastapi.tiangolo.com/) | REST API for the pipeline |
| **Frontend** | [Streamlit](https://streamlit.io/) | Chat UI |
| **Config** | [python-dotenv](https://github.com/theskumar/python-dotenv) | Environment variable management |

---

## How Endee Vector Database is Used

**Endee** is the backbone of RepoMind's semantic search layer. It is an open-source, high-performance vector database engineered for production AI retrieval workloads — and the same project this codebase lives in.

### Index Configuration

```python
client.create_index(
    name="repomind",
    dimension=384,             # all-MiniLM-L6-v2 output size
    space_type="cosine",       # semantic similarity metric
    precision=Precision.INT8,  # compressed for speed
)
```

### Storing Vectors

Each code chunk is stored with its embedding plus rich metadata:

```python
index.upsert([{
    "id": chunk["chunk_id"],
    "vector": chunk["embedding"],
    "meta": {
        "file_path": chunk["file_path"],
        "chunk_id":  chunk["chunk_id"],
        "content":   chunk["content"],
    }
}])
```

### Semantic Search

```python
results = index.query(vector=query_embedding, top_k=5)
# Returns: id, similarity score, and metadata for each match
```

**Why Endee for RepoMind?**
- **Sub-millisecond retrieval** even over large codebases
- **Metadata filtering** — can be extended to filter by file type or path prefix
- **INT8 quantization** — smaller index, faster search, minimal accuracy loss
- **No external SaaS dependency** — runs locally alongside the app via Docker

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- Docker (to run Endee)
- An OpenAI API key (or any LangChain-supported LLM provider)

### 1. Clone the repository

```bash
git clone https://github.com/Archisman-NC/endee.git
cd endee
```

### 2. Start Endee vector database

```bash
# Option A: Docker Hub (fastest)
docker run --ulimit nofile=100000:100000 \
  -p 8080:8080 -v ./endee-data:/data \
  --name endee-server endeeio/endee-server:latest

# Option B: Build from source + Docker Compose (Apple Silicon)
docker build --build-arg BUILD_ARCH=neon -t endee-oss:latest -f ./infra/Dockerfile .
docker compose up -d
```

### 3. Create a Python virtual environment

```bash
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
# LLM (required)
OPENAI_API_KEY=sk-...

# Optional — LangChain model config
LLM_MODEL=gpt-4o-mini
LLM_PROVIDER=openai

# Optional — Endee connection
ENDEE_BASE_URL=http://localhost:8080/api/v1
ENDEE_AUTH_TOKEN=
```

### 5. Launch the app

```bash
streamlit run frontend/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Example Queries

After indexing a repository (e.g. `https://github.com/pallets/flask`), try:

| Query | What RepoMind finds |
|---|---|
| `How are routes defined?` | `app.py` — `@app.route` decorator usage and routing internals |
| `How does authentication work?` | `auth.py` — JWT verification and token handling flow |
| `Where is error handling implemented?` | Exception handler decorators and error blueprint |
| `How does the app handle configuration?` | `config.py` — config object hierarchy and loading logic |
| `Explain the request lifecycle` | Middleware, before/after request hooks, and signal dispatch |

---

## Project Structure

```
endee/
├── ingestion/
│   ├── github_loader.py     # Clone repos with GitPython
│   └── code_chunker.py      # Language-aware code splitting
├── rag/
│   ├── embeddings.py        # Sentence-transformer embedding generation
│   ├── vector_store.py      # Endee DB client — store & search
│   ├── retriever.py         # Query → embed → vector search pipeline
│   └── generator.py         # LangChain LLM answer generation
├── frontend/
│   └── app.py               # Streamlit chat UI
├── tests/
│   ├── test_clone.py
│   ├── test_chunking.py
│   ├── test_embeddings.py
│   ├── test_vector_store.py
│   ├── test_retrieval.py
│   └── test_generation.py
├── requirements.txt
└── .env                     # (not committed)
```

---

## Future Improvements

| Improvement | Description |
|---|---|
| 🔍 **Hybrid Search** | Combine dense + sparse (BM25) retrieval using Endee's sparse vector support for better precision on exact symbol names |
| 🗂️ **File-type Filtering** | Use Endee metadata filters to scope queries to specific languages or directories |
| 🔄 **Incremental Indexing** | Detect changed files via `git diff` and re-embed only modified chunks |
| 🔐 **Private Repo Support** | Accept a GitHub PAT to index private repositories |
| 📊 **Multi-repo Support** | Index multiple repos into separate Endee indexes and query across them |
| 🧩 **IDE Plugin** | VS Code extension that surfaces RepoMind answers inline while coding |
| ⚡ **Streaming Responses** | Stream LLM tokens to the Streamlit UI for faster perceived response time |
| 📈 **Usage Analytics** | Track which queries are made and which code chunks are most frequently retrieved |

---

## License

This project is part of the [Endee](https://endee.io/) open-source vector database ecosystem and is licensed under the **Apache License 2.0**. See the [LICENSE](../LICENSE) file for details.
