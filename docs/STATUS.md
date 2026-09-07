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
| **Phase 4** | **RAG Query Engine** | Semantic vs SQL query router, vector retrieval + **Hybrid Structural Search (Author/TOC)**, Text-to-SQL generator & safe execution with 1-shot self-healing repair, deterministic citations, token streaming via SSE, automatic Gemini -> Groq quota fallback. | Completed & Verified |
| **Phase 5** | **Full Frontend UI** | Two-pane dashboard (upload + chat), collection switcher, live progress bar, proactive insights cards, clickable citation preview modal & SQL inspector. | Completed & Verified |
| **Buffer** | **Polish & Final Verification** | End-to-end integration testing, edge cases, error resilience, README & API documentation polish. | Completed & Verified |

---

## 2. Phase-by-Phase Detail & Verification

### Phase 1 - Foundation & Scaffold - Completed & Verified
- FastAPI entrypoint (`app/main.py`) with lifespan DB connection pool, graceful shutdown, and CORS middleware.
- Hand-written `asyncpg` raw SQL pool with automatic `pgvector` extension detection (`app/core/database.py`).
- Dynamic DDL schema migration ensuring tables (`collections`, `documents`, `document_pages`, `chunks`, `csv_tables`) and HNSW vector index creation (`app/db/schema.py`).
- Health check endpoint `GET /health` responding 200 OK and verifying database connectivity & pgvector readiness.
- React + Vite + Tailwind frontend scaffold with official **shadcn/ui** off-white & black theme.
- Branded as **Weave** with multi-tenant collection architecture.

---

### Phase 2 - PDF Pipeline - Completed & Verified
- Ingestion verified with 708-page and 870-page PDFs.
- PyMuPDF per-page text extraction with automatic 150 DPI Tesseract OCR fallback for scanned/image pages.
- Page-bounded chunker preserving strict `{source_file, page_num, char_offset}` metadata.
- Batch embedding with `all-MiniLM-L6-v2` into 384-dimensional pgvector records.
- SSE progress stream (`GET /ingest/progress/{job_id}`).
- Page-by-page full-text viewer endpoint (`GET /document/{id}/text`).

---

### Phase 3 - CSV Pipeline - Completed & Verified
- Ingested 1,008-row financial benchmark dataset (`test_financial_benchmark.csv`).
- Dual-path CSV ingestion pipeline (semantic row embeddings + dynamic typed PostgreSQL table `csv_doc_<hex>`).
- Column type inference parsing currency (`$1,304.12`, `-$81.55`), percentages (`24.08%`), numbers, booleans, and nulls.
- Schema introspection and preview endpoints (`GET /document/{id}/csv-schema`, `GET /document/{id}/csv-preview`).
- Dynamic cascade deletion dropping dynamic tables on document delete.

---

### Phase 4 - Query Engine - Completed & Verified
- Semantic vs SQL query router classifying qualitative vs analytical questions.
- Hybrid structural vector retrieval (TOC & front-matter chunk enrichment for book metadata/author queries).
- Dynamic Text-to-SQL generator with 1-shot self-healing repair on syntax/nesting errors.
- Mechanically-attached deterministic citations without LLM hallucination.
- Token-by-token SSE streaming (`POST /chat`) and dual LLM fallback layer (Gemini -> Groq on 429 quota exhaustion).

---

### Phase 5 - Full Frontend UI - Completed & Verified
- Minimalist off-white & black design system (shadcn/ui + Tailwind CSS + Poppins font).
- Multi-tenant collection switcher with modal creation.
- Ingestion zone with drag-and-drop & live multi-stage animated progress bars.
- Interactive chat panel with route badges (`Semantic Retrieval` vs `SQL Aggregation`), token streaming, and clickable citation modal displaying source snippets, page numbers, and executed SQL.

---

### Buffer - Polish & Final Verification - Completed & Verified
- End-to-end multi-query stress-testing with 1-shot self-healing verification.
- Documentation, API verification, and performance tuning complete.