import asyncio
import json
import logging
from typing import Any, Dict, List
from uuid import UUID

from app.core.config import get_settings
from app.core.database import db
from app.services.csv_parser import parse_csv_bytes
from app.services.embedding import embedding_service
from app.services.job_manager import job_manager

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


async def process_csv_document(
    document_id: str,
    collection_id: str,
    filename: str,
    csv_bytes: bytes,
    job_id: str,
) -> None:
    """
    Asynchronous dual-path CSV ingestion pipeline:
    1. Parsing: Parse CSV, sanitize column headers, infer PostgreSQL data types.
    2. Path B (SQL Aggregation): Dynamically create typed PostgreSQL table and batch-insert raw rows.
    3. Path A (Semantic Search): Serialize rows into natural language sentences, batch embed (384-dim), store in chunks table.
    4. Done: Register table metadata in csv_tables and update document status.
    """
    try:
        # --- Stage 1: Parsing ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="parsing",
            progress_percent=15,
            message=f"Parsing CSV '{filename}' and inferring column data types...",
        )

        col_defs, parsed_rows, serialized_sentences = await asyncio.to_thread(
            parse_csv_bytes, csv_bytes
        )
        total_rows = len(parsed_rows)

        # Update document row count
        await db.execute(
            "UPDATE documents SET total_pages = $1 WHERE id = $2;",
            total_rows,
            UUID(document_id),
        )

        # --- Stage 2: Path B - Raw SQL Table Creation & Data Loading ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="storing",
            progress_percent=35,
            message=f"Creating typed PostgreSQL table for '{filename}' ({total_rows} rows)...",
            total_pages=total_rows,
        )

        clean_doc_id = document_id.replace("-", "")
        dynamic_table_name = f"csv_doc_{clean_doc_id}"

        # Build CREATE TABLE DDL
        col_ddl_parts = [
            f'"{col.name}" {col.data_type}'
            for col in col_defs
        ]
        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS "{dynamic_table_name}" (
            _row_id SERIAL PRIMARY KEY,
            collection_id UUID NOT NULL,
            document_id UUID NOT NULL,
            {', '.join(col_ddl_parts)},
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
        """
        await db.execute(create_table_sql)

        # Build parameterized INSERT query
        col_names_quoted = [f'"{col.name}"' for col in col_defs]
        col_placeholders = [f"${i+3}" for i in range(len(col_defs))]

        insert_sql = f"""
        INSERT INTO "{dynamic_table_name}" (collection_id, document_id, {', '.join(col_names_quoted)})
        VALUES ($1, $2, {', '.join(col_placeholders)});
        """

        # Prepare batch insert records
        batch_records = []
        for row_dict in parsed_rows:
            record_values = [UUID(collection_id), UUID(document_id)]
            for col in col_defs:
                record_values.append(row_dict.get(col.name))
            batch_records.append(tuple(record_values))

        await db.execute_many(insert_sql, batch_records)

        # Register table in csv_tables registry
        col_defs_json = json.dumps([c.model_dump() for c in col_defs])
        await db.execute(
            """
            INSERT INTO csv_tables (document_id, collection_id, table_name, row_count, column_definitions)
            VALUES ($1, $2, $3, $4, $5::jsonb)
            ON CONFLICT (document_id) DO UPDATE 
            SET table_name = EXCLUDED.table_name,
                row_count = EXCLUDED.row_count,
                column_definitions = EXCLUDED.column_definitions;
            """,
            UUID(document_id),
            UUID(collection_id),
            dynamic_table_name,
            total_rows,
            col_defs_json,
        )

        # --- Stage 3: Path A - Row Serialization & Batch Embeddings ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="embedding",
            progress_percent=65,
            message=f"Generating embeddings for {total_rows} serialized CSV rows ({settings.embedding_model})...",
            total_pages=total_rows,
            total_chunks=total_rows,
        )

        embeddings = await asyncio.to_thread(
            embedding_service.embed_texts, serialized_sentences
        )

        # --- Stage 4: Store in chunks table ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="storing",
            progress_percent=85,
            message=f"Storing {total_rows} row vectors in chunks table...",
            total_pages=total_rows,
            total_chunks=total_rows,
        )

        # Delete any existing chunks for this document
        await db.execute("DELETE FROM chunks WHERE document_id = $1;", UUID(document_id))

        chunk_insert_records = []
        for idx, (sentence, emb) in enumerate(zip(serialized_sentences, embeddings)):
            vector_str = f"[{','.join(str(x) for x in emb)}]"
            chunk_insert_records.append(
                (
                    UUID(document_id),
                    UUID(collection_id),
                    filename,
                    "csv_row",
                    idx + 1,  # 1-indexed row number
                    0,
                    sentence,
                    vector_str,
                )
            )

        await db.execute_many(
            """
            INSERT INTO chunks (document_id, collection_id, source_file, type, page_num, char_offset, content, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8::vector);
            """,
            chunk_insert_records,
        )

        # Mark document completed
        await db.execute(
            "UPDATE documents SET status = 'completed' WHERE id = $1;",
            UUID(document_id),
        )

        # --- Stage 5: Done ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="done",
            progress_percent=100,
            message=f"Successfully ingested {filename}: {total_rows} rows loaded into SQL table '{dynamic_table_name}' and vectorized.",
            total_pages=total_rows,
            total_chunks=total_rows,
        )
        logger.info(f"CSV Document {document_id} ({filename}) ingested successfully into table {dynamic_table_name}.")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error ingesting CSV document {document_id}: {error_msg}", exc_info=True)
        try:
            await db.execute(
                "UPDATE documents SET status = 'failed', error = $1 WHERE id = $2;",
                error_msg,
                UUID(document_id),
            )
        except Exception:
            pass

        await job_manager.emit_event(
            job_id=job_id,
            stage="failed",
            progress_percent=100,
            message=f"CSV ingestion failed: {error_msg}",
            error=error_msg,
        )
