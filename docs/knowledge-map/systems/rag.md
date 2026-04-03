# RAG System

## Minimal
Retrieval-Augmented Generation pipeline: ingest files → chunk → embed → store in SQLite → search with cosine similarity → rerank with cross-encoder → augment prompts.

## Condensed

### Purpose
Gives LLMs access to project-specific knowledge by embedding files into a searchable vector store and injecting relevant context into prompts.

### Components
- **rag.py** — VectorStore (SQLite), RAGPipeline (ingest/retrieve/augment)
- **kb.py** — KnowledgeBase (high-level: ingest_directory, search with reranking)
- **lightrag.py** — LightRAG (unified search across KB + LocalAI /stores/)
- **indexer.py** — AutoIndexer (background file watcher, mtime-based)
- **chunking.py** — Text/file chunking for embeddings
- **stores.py** — LocalAI /stores/ API client (ephemeral working memory)

### Data Flow
```
Files → chunk_file() → embed_batch() → VectorStore.add()
Query → embed() → VectorStore.search() → rerank() → augment_prompt()
```

### Two Storage Layers
1. **VectorStore (SQLite)** — persistent, survives restarts, project KB
2. **LocalAI /stores/** — ephemeral, in-memory, working memory for agents

### Auto-Indexing
Polls project files every 30s, re-embeds changed files. Skips .git, .venv, node_modules.

### Key Config
```yaml
rag.enabled: true
rag.db_path: .aicp/rag.db
rag.chunk_size: 512
rag.rerank: true
rag.auto_index: true
rag.auto_index_interval: 30
backends.local.embedding_model: nomic-embed    # CPU, 0 GPU cost
backends.local.reranker_model: bge-reranker-v2-m3
```
