# YottaFlex — RAG Architecture

## Pipeline

```
Documents → Load → Parse → Chunk (800 chars, 120 overlap)
         → Embed (SentenceTransformers all-MiniLM-L6-v2)
         → ChromaDB (yottaflex_policies collection)
         → Retrieve (top-k by cosine similarity)
         → Groq LLM (grounded with retrieved context)
         → Cited answer
```

## Components

### Embedding Model
- Model: `sentence-transformers/all-MiniLM-L6-v2`
- Runs on CPU (no GPU required)
- Downloaded once, cached locally
- **Never uses OpenAI embeddings**

### Vector Store
- ChromaDB (persistent local storage)
- Collection: `yottaflex_policies`
- Persisted to `./data/chroma/` (Docker volume in compose)

### Document Management
- 7 sample policy documents seeded via `POST /api/rag/documents/seed-samples`
- Categories: SLA_POLICY, CARRIER_POLICY, WEATHER_SOP, FACILITY_SOP, DELAY_HANDLING, ROUTE_CHANGE, ESCALATION
- Supports: TEXT, PDF (via pypdf), DOCX (via python-docx)
- Version tracking in `rag_documents` table
- Ingestion jobs tracked in `rag_ingestion_jobs` table

### Citation Format
Every answer includes:
- Document name
- Version
- Category
- Chunk index (e.g., "chunk 1/3")
- Source excerpt (first 200 chars)

**Never invents citations.** If no supporting content is found: "No supporting policy information was found."

## API

```powershell
# Search policies
POST /api/rag/search
{"query": "What is the SLA policy for delays?", "n_results": 5}

# Create document
POST /api/rag/documents
{"document_name": "Custom Policy", "category": "OTHER", "content_text": "..."}

# Re-ingest after edit
POST /api/rag/documents/{id}/reingest
```
