import logging
from app.core.database import db

logger = logging.getLogger("uvicorn.error")

SCHEMA_SQL = """
-- 1. Enable pgvector and uuid extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Collections table (Multi-tenancy namespace)
CREATE TABLE IF NOT EXISTS collections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id UUID NOT NULL REFERENCES collections(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    type TEXT NOT NULL, -- 'pdf' or 'csv'
    status TEXT NOT NULL DEFAULT 'processing', -- 'processing', 'completed', 'failed'
    total_pages INT DEFAULT 0, -- For PDF: page count; For CSV: row count
    file_size INT DEFAULT 0,
    error TEXT,
    uploaded_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT uq_documents_id_collection UNIQUE (id, collection_id)
);

-- 4. Document full text by page (for Section 3.5 Full-Text rendering)
-- Composite foreign key guarantees page.collection_id strictly matches document.collection_id
CREATE TABLE IF NOT EXISTS document_pages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    collection_id UUID NOT NULL,
    page_num INT NOT NULL,
    text TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_doc_page UNIQUE (document_id, page_num),
    CONSTRAINT fk_document_pages_document FOREIGN KEY (document_id, collection_id) 
        REFERENCES documents(id, collection_id) ON DELETE CASCADE
);

-- 5. Chunks table with 384-dim pgvector column (for PDF chunks & CSV row-to-text vectors)
-- Composite foreign key guarantees chunks.collection_id strictly matches parent document.collection_id,
-- preventing cross-tenant data leakage at the database constraint level while maintaining fast unjoined vector search.
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL,
    collection_id UUID NOT NULL,
    source_file TEXT NOT NULL,
    type TEXT NOT NULL DEFAULT 'pdf', -- 'pdf' or 'csv_row'
    page_num INT NOT NULL, -- For PDF: 1-indexed page; For CSV: 1-indexed row number
    char_offset INT NOT NULL DEFAULT 0,
    content TEXT NOT NULL,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_chunks_document FOREIGN KEY (document_id, collection_id) 
        REFERENCES documents(id, collection_id) ON DELETE CASCADE
);

-- 6. CSV Tables registry (tracks dynamically created SQL tables per CSV for SQL Aggregation path)
CREATE TABLE IF NOT EXISTS csv_tables (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL UNIQUE,
    collection_id UUID NOT NULL,
    table_name TEXT NOT NULL UNIQUE,
    row_count INT NOT NULL DEFAULT 0,
    column_definitions JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT fk_csv_tables_document FOREIGN KEY (document_id, collection_id) 
        REFERENCES documents(id, collection_id) ON DELETE CASCADE
);

-- 7. Indexes for performance
CREATE INDEX IF NOT EXISTS idx_collections_name ON collections(name);
CREATE INDEX IF NOT EXISTS idx_documents_collection_id ON documents(collection_id);
CREATE INDEX IF NOT EXISTS idx_doc_pages_doc_page ON document_pages(document_id, page_num);
CREATE INDEX IF NOT EXISTS idx_chunks_collection_id ON chunks(collection_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_csv_tables_doc ON csv_tables(document_id);
CREATE INDEX IF NOT EXISTS idx_csv_tables_col ON csv_tables(collection_id);

-- 8. HNSW Cosine vector index on chunks
CREATE INDEX IF NOT EXISTS idx_chunks_embedding_hnsw 
ON chunks USING hnsw (embedding vector_cosine_ops);
"""


async def init_schema() -> None:
    """Initialize database tables and create default collection idempotently."""
    logger.info("Initializing database schema and pgvector tables...")
    try:
        await db.execute(SCHEMA_SQL)
        logger.info("Database schema initialized successfully.")

        # Ensure a default collection exists idempotently (single atomic query)
        await db.execute(
            "INSERT INTO collections (name, description) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING;",
            "Default",
            "Default collection for uploaded documents",
        )
        logger.info("Default collection ready.")
    except Exception as e:
        logger.error(f"Error initializing database schema: {e}")
        raise e

