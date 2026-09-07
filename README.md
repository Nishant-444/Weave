# Weave - Production Multi-Tenant PDF & CSV RAG System

A production-grade, framework-free Retrieval-Augmented Generation (RAG) system engineered for high-accuracy document intelligence across complex PDFs and structured CSV datasets.

Featuring **mechanically-attached deterministic citations**, **dual-path CSV text-to-SQL aggregation**, **hybrid structural search with OCR fallback**, **dual-provider LLM failover**, **multi-tenant collection isolation**, and **real-time Server-Sent Events (SSE) streaming**.

---

## Key Highlights & Architectural Innovations

- **Deterministic Non-Hallucinated Citations**: Citations are generated strictly from retrieval and database execution metadata-never hallucinated by the LLM. Every citation links to an exact PDF page number, character offset, CSV row, or executed SQL query.
- **Dual-Path CSV Ingestion & Execution**:
  - **Path A (Semantic Search)**: Every CSV row is serialized into natural language and embedded into 384-dimensional dense vectors in `pgvector`.
  - **Path B (Live SQL Aggregation)**: Type inference automatically parses currencies (`$1,304.12`, `-$81.55`), percentages (`24.08%`), numbers, and dates into dynamic typed PostgreSQL tables (`csv_doc_<doc_id_hex>`) for exact calculation queries (`SUM`, `AVG`, `ROUND`, `GROUP BY`).
- **Hybrid Structural Search & OCR Fallback**:
  - Automatically captures document structure (Title, Front-matter, Table of Contents) ensuring accurate answers to macro-level queries (*"who is the author"*, *"list all chapters"*).
  - High-resolution **Tesseract OCR fallback** for scanned pages, diagrams, and non-selectable image text.
- **Dual-Provider LLM Resilience Layer**:
  - Primary provider: Google Gemini (`gemini-3.6-flash`).
  - Automatic pre-stream failover to Groq (`openai/gpt-oss-120b` / `llama-3.3-70b-versatile`) upon rate limits (`429`, `RESOURCE_EXHAUSTED`).
- **Multi-Tenant Collections**: Full data isolation across collections-every table, chunk, and dynamic SQL table is partitioned by `collection_id`.
- **Minimalist Off-White & Black Frontend**: Built with React 18, TypeScript, Vite, Tailwind CSS, and shadcn/ui. Features a live ingestion zone with multi-stage progress tracking, full-text PDF viewer, CSV tabular preview, token-streaming chat, and an interactive citation drawer.

---

## System Architecture

### 1. Ingestion Pipeline Architecture

```
                                  ┌────────────────────────┐
                                  │      POST /upload      │
                                  └───────────┬────────────┘
                                              │
                       ┌──────────────────────┴──────────────────────┐
                       │ (PDF Document)                              │ (CSV Dataset)
                       ▼                                             ▼
        ┌─────────────────────────────┐               ┌─────────────────────────────┐
        │      PyMuPDF Extractor      │               │     CSV Type Inferencer     │
        │  • Per-page text extraction │               │  • Currency, %, dates, bools│
        │  • Tesseract OCR Fallback   │               │  • Sanitize column headers  │
        └──────────────┬──────────────┘               └──────────────┬──────────────┘
                       │                                             │
                       ▼                                             ├─────────────────────────────┐
        ┌─────────────────────────────┐                              ▼ (Path A)                    ▼ (Path B)
        │    Page-Bounded Chunker     │               ┌─────────────────────────────┐ ┌─────────────────────────────┐
        │  • ~1500 chars / 200 overlap│               │    Row-to-Text Serializer   │ │    Dynamic Postgres Table   │
        │  • Page & offset metadata   │               │  • Key-value representation │ │  • csv_doc_<id> created     │
        └──────────────┬──────────────┘               └──────────────┬──────────────┘ │  • Batch rows inserted      │
                       │                                             │                └─────────────────────────────┘
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │     Embedding Pipeline      │
                               │  • all-MiniLM-L6-v2 (local) │
                               │  • 384-dimensional vectors  │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │   Supabase / PostgreSQL     │
                               │  • pgvector HNSW Index      │
                               │  • SSE Progress Broadcast   │
                               └─────────────────────────────┘
```

### 2. RAG Query Engine & Streaming Flow

```
                               ┌─────────────────────────────┐
                               │   POST /chat (User Query)   │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │        Query Router         │
                               │  • Semantic vs SQL Decision │
                               └──────────────┬──────────────┘
                                              │
                       ┌──────────────────────┴──────────────────────┐
                       │ (Semantic Query)                            │ (Aggregation Query)
                       ▼                                             ▼
        ┌─────────────────────────────┐               ┌─────────────────────────────┐
        │   Hybrid Semantic Engine    │               │    SQL Aggregation Engine   │
        ├─────────────────────────────┤               ├─────────────────────────────┤
        │ • 384-dim query embedding   │               │ • Schema introspection in   │
        │ • Cosine similarity search  │               │   csv_tables registry       │
        │ • TOC & structural chunks   │               │ • Text-to-SQL (Gemini/Groq) │
        │ • Grounded context builder  │               │ • Safe execution in Postgres│
        │ • Mechanical page citations │               │ • Mechanical SQL citation   │
        └──────────────┬──────────────┘               └──────────────┬──────────────┘
                       │                                             │
                       └──────────────────────┬──────────────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │   SSE Streaming Response    │
                               │  1. event: routing          │
                               │  2. event: token (stream)   │
                               │  3. event: citations        │
                               │  4. event: done             │
                               └─────────────────────────────┘
```

---

## Repository Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── __init__.py          # API router registry
│   │   │   ├── chat.py              # POST /chat (SSE streaming & citation delivery)
│   │   │   ├── collections.py       # GET, POST, GET /{id} /collections
│   │   │   ├── documents.py         # GET /documents, GET text/schema/preview, DELETE
│   │   │   ├── health.py            # GET /health (Database & pgvector status)
│   │   │   └── ingest.py            # POST /upload, GET /ingest/progress/{job_id} (SSE)
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic Settings (LLMs, DB, CORS, Embeddings)
│   │   │   └── database.py          # Raw SQL asyncpg connection pool & helpers
│   │   ├── db/
│   │   │   └── schema.py            # DDL: collections, documents, pages, chunks, csv_tables
│   │   ├── models/
│   │   │   ├── chat.py              # ChatRequest, Citation, RoutingDecision
│   │   │   ├── chunk.py             # Vector Chunk models
│   │   │   ├── collection.py        # Collection schemas
│   │   │   ├── csv_table.py         # CSVSchema & CSVPreview models
│   │   │   ├── document.py          # Document, DocumentPage, UploadResponse
│   │   │   ├── health.py            # Health status schema
│   │   │   └── job.py               # Ingestion progress events
│   │   ├── services/
│   │   │   ├── csv_ingest_pipeline.py # Dual-path CSV ingestion orchestrator
│   │   │   ├── csv_parser.py        # Type inference, column sanitization, row serializer
│   │   │   ├── embedding.py         # sentence-transformers 384-dim batch embedder
│   │   │   ├── ingest_pipeline.py   # PDF ingestion orchestrator
│   │   │   ├── job_manager.py       # SSE progress tracking pub/sub
│   │   │   ├── llm_service.py       # LLM provider wrapper
│   │   │   ├── pdf_parser.py        # PyMuPDF extractor + Tesseract OCR fallback
│   │   │   ├── query_router.py      # Semantic vs. SQL classifier
│   │   │   ├── semantic_engine.py   # Vector retrieval + structural TOC enrichment
│   │   │   └── sql_engine.py        # Text-to-SQL generation & Postgres execution
│   │   ├── llm.py                   # Dual LLM resilience layer (Gemini -> Groq failover)
│   │   └── main.py                  # FastAPI entrypoint, lifespan & CORS
│   ├── .env.example
│   ├── pyproject.toml
│   └── requirements.txt
├── docs/
│   ├── PRD.md                       # Product Requirements Document
│   └── STATUS.md                    # Project Status & Milestone Tracker
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn/ui primitives (badge, button, input, separator)
│   │   │   ├── ChatPanel.tsx        # Streaming chat panel with route badge & citation chips
│   │   │   ├── CitationModal.tsx    # Modal for inspecting citation snippets & SQL queries
│   │   │   ├── DocumentInspectorModal.tsx # Full-text PDF reader & CSV schema/data preview
│   │   │   ├── DocumentList.tsx     # Active documents list with inspection and deletion
│   │   │   ├── Header.tsx           # Navigation, collection selector, and health badge
│   │   │   ├── IngestionZone.tsx    # File drag-and-drop & live multi-stage progress
│   │   │   └── NewCollectionModal.tsx # Dialog to create isolated tenant collections
│   │   ├── lib/
│   │   │   └── utils.ts             # Tailwind class merging utility
│   │   ├── types/
│   │   │   └── index.ts             # TypeScript interfaces
│   │   ├── App.tsx                  # Main application state orchestrator
│   │   ├── index.css                # Global styles & design system tokens
│   │   └── main.tsx                 # React DOM mount point
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── test_financial_benchmark.csv     # 1,008-row benchmark dataset for CSV validation
└── README.md
```

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Node.js 18+** and **pnpm** (or npm)
- **PostgreSQL with pgvector** (e.g. Supabase or local PostgreSQL instance)
- **Tesseract OCR** (for scanned PDF image extraction):
  ```bash
  # Debian / Ubuntu
  sudo apt-get update && sudo apt-get install -y tesseract-ocr
  # macOS
  brew install tesseract
  ```

---

### Backend Setup

1. **Navigate to the backend directory and set up a virtual environment:**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables:**
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your credentials:
   ```ini
   APP_ENV=development
   DATABASE_URL=postgresql://postgres:password@localhost:5432/postgres
   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_MODEL_NAME=gemini-3.6-flash
   GROQ_API_KEY=your_groq_api_key
   GROQ_MODEL_NAME=openai/gpt-oss-120b
   ```

4. **Start the FastAPI development server:**
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
   The backend will automatically connect to PostgreSQL and initialize all database tables and the `pgvector` extension.
   - Interactive Swagger API Docs: `http://localhost:8000/docs`
   - Health Check: `http://localhost:8000/health`

---

### Frontend Setup

1. **Navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install dependencies:**
   ```bash
   pnpm install
   ```

3. **Start the Vite development server:**
   ```bash
   pnpm dev
   ```
   The UI will be accessible at `http://localhost:5173`. API calls to `/api/*` are automatically proxied to the backend at `http://localhost:8000`.

---

## API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | Verifies database connectivity, pgvector extension, and LLM readiness. |
| `GET` | `/collections` | Lists all collections with associated document counts. |
| `POST` | `/collections` | Creates a new collection namespace (`{"name": "...", "description": "..."}`). |
| `GET` | `/collections/{id}` | Fetches metadata for a specific collection. |
| `POST` | `/upload` | Multipart upload for `.pdf` or `.csv` files. Returns `document_id` and `job_id`. |
| `GET` | `/ingest/progress/{job_id}` | SSE stream emitting live ingestion stage events (`parsing` -> `chunking` -> `embedding` -> `done`). |
| `GET` | `/documents` | Lists uploaded documents for a collection (`?collection_id=<UUID>`). |
| `GET` | `/document/{id}/text` | Returns the complete page-by-page extracted text of an ingested PDF. |
| `GET` | `/document/{id}/csv-schema` | Returns the dynamic PostgreSQL table name and inferred column definitions. |
| `GET` | `/document/{id}/csv-preview` | Previews the raw typed rows from the dynamic PostgreSQL table (`?limit=20`). |
| `DELETE` | `/document/{id}` | Cascades document deletion, chunks, and automatically drops dynamic CSV tables. |
| `POST` | `/chat` | SSE stream for chat query execution with token streaming and deterministic citations. |

---

## Verification & Example Queries

### 1. Semantic Vector Q&A (PDFs & Qualitative CSVs)

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What are the core approaches for solving dynamic programming questions?",
    "collection_id": "Default"
  }'
```

**SSE Stream Output:**
```
event: routing
data: {"route": "semantic", "reason": "Query is conceptual and qualitative; routed to semantic vector retrieval."}

event: token
data: {"token": "For"}

event: token
data: {"token": " dynamic programming, the two primary patterns are..."}

event: citations
data: {"citations": [{"id": 1, "source_file": "Cracking-the-coding-interview.pdf", "page_num": 105, "type": "pdf", "snippet": "Dynamic Programming is mainly an optimization over plain recursion..."}]}

event: done
data: {"status": "completed", "route": "semantic"}
```

---

### 2. SQL Aggregation Q&A (Tabular Financial CSVs)

```bash
curl -N -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the total revenue and average operating margin for Apex Systems across all quarters?",
    "collection_id": "Default"
  }'
```

**SSE Stream Output:**
```
event: routing
data: {"route": "sql", "reason": "Query requests statistical calculation and aggregation; routed to SQL engine."}

event: token
data: {"token": "Based on the database records [1], for **Apex Systems Inc.** across all quarters:\n\n- **Total Revenue:** $33,240.50M\n- **Average Operating Margin:** 16.42%"}

event: citations
data: {"citations": [{"id": 1, "source_file": "test_financial_benchmark.csv", "type": "sql_query", "snippet": "Computed from 1 matching row(s) in PostgreSQL table 'csv_doc_8f1b2c4a'.", "sql_query": "SELECT SUM(\"total_revenue_m\") AS total_revenue, ROUND(AVG(\"operating_margin\"), 2) AS avg_margin FROM \"csv_doc_8f1b2c4a\" WHERE \"company_name\" ILIKE '%Apex Systems%';"}]}

event: done
data: {"status": "completed", "route": "sql"}
```

---

## Project Milestones & Roadmap

- **Phase 1: Foundation & Scaffold**: FastAPI app lifespan, typed config, `asyncpg` raw connection pool, `pgvector` auto-setup, health check, shadcn off-white & dark theme.
- **Phase 2: PDF Ingestion Pipeline**: PyMuPDF extraction, high-resolution **Tesseract OCR fallback**, page-bounded chunking, batch embedding, pgvector storage, SSE progress events, full-text viewer.
- **Phase 3: CSV Ingestion Pipeline**: Dual-path processing (row embeddings + dynamic typed PostgreSQL table), currency/percentage type inference, schema introspection & preview endpoints.
- **Phase 4: RAG Query Engine**: Query router (semantic vs. SQL), hybrid structural retrieval (author/TOC enrichment), safe text-to-SQL execution, deterministic citations, token-by-token SSE streaming, dual LLM failover (Gemini -> Groq).
- **Phase 5: Full Frontend UI**: Responsive two-pane dashboard, multi-collection switcher, drag-and-drop uploader with live progress bars, document inspector modal (PDF page reader & CSV table viewer), interactive citation chips & SQL query inspection modal.
- **Polish & Final Verification**: End-to-end integration verified, strict error resilience, typed boundaries, and comprehensive documentation.

---

## License

MIT License. Designed and engineered for high-accuracy document intelligence and enterprise RAG compliance.
