# Weave - Project Status & Roadmap Tracker

**Last Updated:** August 28, 2026  
**Reference PRD:** [PRD.md](./PRD.md)  
**System Architecture:** FastAPI (Async/Raw SQL) + PostgreSQL (pgvector) + sentence-transformers (384-dim) + Dual LLM (Gemini / Groq) + React 18 (TypeScript + Vite + Tailwind + shadcn/ui)

---

## 1. Overall Progress Overview

| Phase | Milestone | Scope / Deliverable | Status |
| :--- | :--- | :--- | :---: |
| **Phase 1** | **Foundation & Scaffold** | FastAPI + React skeleton, typed config, `asyncpg` + `pgvector` health check, shadcn off-white/black UI. | Completed & Verified |
| **Phase 2** | **PDF Ingestion Pipeline** | `/upload` endpoint, PyMuPDF extraction + **Tesseract OCR Fallback for image-based/scanned pages**, chunking, `all-MiniLM-L6-v2` embeddings, pgvector storage, SSE progress events, full-text viewer. | Completed & Verified |
| **Phase 3** | **CSV Ingestion Pipeline** | CSV upload, dual path (row-to-text vector embeddings + dynamic typed Postgres table for SQL aggregation), type inference, schema & preview APIs. | Completed & Verified |
| **Phase 4** | **RAG Query Engine** | Semantic vs SQL query router, vector retrieval + **Hybrid Structural Search (Author/TOC)**, Text-to-SQL generator & safe execution, deterministic citations, token streaming via SSE, automatic Gemini -> Groq quota fallback. | Completed & Verified |
| **Phase 5** | **Full Frontend UI** | Two-pane dashboard (upload + chat), collection switcher, live progress bar, proactive insights cards, clickable citation preview modal & SQL inspector. | Completed & Verified |
| **Buffer** | **Polish & Final Verification** | End-to-end integration testing, edge cases, error resilience, README & API documentation polish. | Completed & Verified |

---

## 2. Phase-by-Phase Detail & Verification

### Phase 1 - Foundation & Scaffold - Completed & Verified
- FastAPI entrypoint (`app/main.py`) with lifespan DB connection pool, graceful shutdown, and CORS middleware.
- Hand-written `asyncpg` raw SQL pool with automatic `pgvector` extension detection (`app/core/database.py`).
- Dynamic DDL schema migration ensuring tables (`collections`, `documents`, `document_pages`, `chunks`, `csv_tables`) and HNSW vector index creation (`app/db/schema.py`).
- Health check endpoint `GET /health` verifying database connectivity and pgvector readiness.
- React + Vite + Tailwind frontend scaffold with official **shadcn/ui** off-white & black theme.
- Branded as **Weave** with multi-tenant collection architecture.

---

### Phase 2 - PDF Pipeline - Completed & Verified
- Ingestion verified with 708-page textbook (`Cracking-the-coding-interview.pdf`).
- **Tesseract OCR Integration**: Automatic high-resolution OCR fallback for scanned pages, infographics, diagrams, and non-selectable image text (`app/services/pdf_parser.py`).
- Page-bounded chunker preserving exact `{source_file, page_num, char_offset}` metadata.
- Batch embedding using local `sentence-transformers` (`all-MiniLM-L6-v2`) generating 384-dimensional dense vectors.
- Native pgvector storage with cosine similarity indexing.
- Broadcasted real-time stage transitions via SSE stream (`GET /ingest/progress/{job_id}`).
- Page-by-page text rendering endpoint verified (`GET /document/{id}/text`).

---

### Phase 3 - CSV Pipeline - Completed & Verified
- Ingested 1,008-row benchmark dataset (`test_financial_benchmark.csv`).
- Inferred column types across complex currency strings (`$1,304.12`, `-$81.55`), percentages (`24.08%`), booleans, integers, floats, dates, and nulls (`app/services/csv_parser.py`).
- Created dynamic typed PostgreSQL table (`csv_doc_<doc_id_hex>`) and batch-inserted structured records.
- Batch-embedded 1,008 row natural-language serializations into `chunks` with `type = 'csv_row'`.
- Verified live multi-stage progress via SSE stream (`GET /ingest/progress/{job_id}`).
- Verified schema and data preview endpoints (`GET /document/{id}/csv-schema`, `GET /document/{id}/csv-preview`).
- Dynamic cascade deletion with automated table drop (`DELETE /document/{id}`).

---

### Phase 4 - Query Engine - Completed & Verified
- **Dual Provider LLM Fallback Layer (`app/llm.py`)**:
  - `stream_llm_response` and `generate_llm_text` try primary Google Gemini (`gemini-3.6-flash`).
  - Automatically intercepts pre-stream quota errors (`429`, `RESOURCE_EXHAUSTED`, `rate limit`) and fails over seamlessly to Groq (`openai/gpt-oss-120b`).
- **Query Router (`app/services/query_router.py`)**:
  - LLM classifier with heuristic backup categorizing questions into `semantic` (qualitative/conceptual) vs `sql` (numeric aggregation, averages, sums, top-N).
- **Hybrid Structural Retrieval (`app/services/semantic_engine.py`)**:
  - Combines 384-dim vector similarity with front-matter & Table of Contents structural chunk enrichment.
  - Accurate answers for book metadata queries (*"who is the author"*, *"tell the contents"*, *"complete chapter names"*).
- **SQL Aggregation Engine (`app/services/sql_engine.py`)**:
  - Dynamic PostgreSQL schema introspection.
  - Text-to-SQL generation with safe read-only SQL execution (`SELECT`, `SUM`, `AVG`, `ROUND`, `GROUP BY`).
  - Real calculations executed on Postgres - guaranteed zero hallucinated math.
- **Mechanically-Attached Deterministic Citations**:
  - Attached directly from retrieval/execution metadata: exact PDF page numbers, char offsets, row references, and executed SQL statements.
- **SSE Token Streaming (`POST /chat`)**:
  - Structured event sequence: `routing` -> `token` (streamed chunks) -> `citations` (metadata) -> `done`.

---

### Phase 5 - Full Frontend UI - Completed & Verified
- **Minimalist Off-White & Black Design System**:
  - Custom styled with Tailwind CSS, shadcn/ui components, and clean Poppins typography.
  - Responsive two-pane layout with subtle borders and micro-interactions.
- **Collection Switcher & Multi-Tenancy**:
  - Dropdown navigation with active collection indicators and "+ New Collection" modal dialog.
  - Full data isolation across collections.
- **Left Ingestion Zone & Document Explorer**:
  - Drag-and-drop file uploader supporting `.pdf` and `.csv`.
  - Multi-stage animated progress bar (`parsing` -> `chunking`/`storing` -> `embedding` -> `done`).
  - Active documents listing with document type badges, chunk counters, and deletion support.
  - Document Inspector Modal: Page-by-page full text reader for PDFs + live SQL schema & tabular data preview for CSVs.
- **Right Interactive Chat & Citation System**:
  - Real-time token streaming with animated typing state.
  - Dynamic route badge (`Semantic Retrieval` vs `SQL Aggregation`).
  - Markdown message rendering with formatted tables and code blocks.
  - Clickable citation chips (`[1]`, `[2]`) opening an inspection modal displaying exact source file, page number, preview snippet, and executed SQL query.

---

### Polish & Final Verification - Completed & Verified
- Verified full build and typecheck on frontend (`pnpm build`).
- Verified backend async lifespan, CORS, and connection pool handling.
- Tested graceful fallbacks when LLM quota or connection is constrained.
- Updated all documentation, API reference, and setup guides.
