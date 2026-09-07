import asyncio
import logging
from typing import List
from uuid import UUID

from app.core.config import get_settings
from app.core.database import db
from app.services.pdf_parser import extract_pdf_text_by_pages, chunk_extracted_pages
from app.services.embedding import embedding_service
from app.services.job_manager import job_manager

logger = logging.getLogger("uvicorn.error")
settings = get_settings()


async def process_pdf_document(
    document_id: str,
    collection_id: str,
    filename: str,
    pdf_bytes: bytes,
    job_id: str,
) -> None:
    """
    Asynchronous end-to-end PDF ingestion pipeline:
    1. Parsing: Extract per-page text via PyMuPDF.
    2. Page Storage: Store page-level full text in document_pages table.
    3. Chunking: Slide-window chunking strictly bound to source page numbers.
    4. Batch Embedding: Generate 384-dimensional vector embeddings with sentence-transformers.
    5. Storage: Insert chunks and vectors into Postgres/pgvector chunks table.
    6. Done: Update document status and emit final progress event.
    """
    try:
        # --- Stage 1: Parsing ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="parsing",
            progress_percent=15,
            message=f"Extracting text from '{filename}' with PyMuPDF...",
        )

        # PyMuPDF extraction in thread pool to avoid blocking async event loop
        pages = await asyncio.to_thread(extract_pdf_text_by_pages, pdf_bytes)
        total_pages = len(pages)

        # Update document page count and store pages in document_pages table
        await db.execute(
            "UPDATE documents SET total_pages = $1 WHERE id = $2;",
            total_pages,
            UUID(document_id),
        )

        page_records = [
            (UUID(document_id), UUID(collection_id), p.page_num, p.text)
            for p in pages
        ]
        await db.execute_many(
            """
            INSERT INTO document_pages (document_id, collection_id, page_num, text)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (document_id, page_num) DO UPDATE SET text = EXCLUDED.text;
            """,
            page_records,
        )

        await job_manager.emit_event(
            job_id=job_id,
            stage="parsing",
            progress_percent=35,
            message=f"Extracted {total_pages} pages successfully.",
            total_pages=total_pages,
        )

        # --- Stage 2: Chunking ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="chunking",
            progress_percent=50,
            message="Chunking text with page boundary preservation...",
            total_pages=total_pages,
        )

        chunks = chunk_extracted_pages(
            pages=pages,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        total_chunks = len(chunks)

        if total_chunks == 0:
            logger.warning(f"Document {document_id} has no extractable text.")
            await db.execute(
                "UPDATE documents SET status = 'completed' WHERE id = $1;",
                UUID(document_id),
            )
            await job_manager.emit_event(
                job_id=job_id,
                stage="done",
                progress_percent=100,
                message="PDF has no extractable text. Ingestion marked complete.",
                total_pages=total_pages,
                total_chunks=0,
            )
            return

        # --- Stage 3: Batch Embeddings ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="embedding",
            progress_percent=65,
            message=f"Generating embeddings for {total_chunks} chunks ({settings.embedding_model})...",
            total_pages=total_pages,
            total_chunks=total_chunks,
        )

        chunk_texts = [c.content for c in chunks]
        # Batch embedding in worker thread
        embeddings = await asyncio.to_thread(embedding_service.embed_texts, chunk_texts)

        # --- Stage 4: Storing in Postgres with pgvector ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="storing",
            progress_percent=85,
            message=f"Storing {total_chunks} chunks and vector embeddings in Postgres...",
            total_pages=total_pages,
            total_chunks=total_chunks,
        )

        # Delete any existing chunks for this document if re-uploading
        await db.execute("DELETE FROM chunks WHERE document_id = $1;", UUID(document_id))

        # Format vector embeddings for pgvector: string representation '[f1, f2, ...]'
        chunk_insert_records = []
        for chunk, emb in zip(chunks, embeddings):
            vector_str = f"[{','.join(str(x) for x in emb)}]"
            chunk_insert_records.append(
                (
                    UUID(document_id),
                    UUID(collection_id),
                    filename,
                    "pdf",
                    chunk.page_num,
                    chunk.char_offset,
                    chunk.content,
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

        # Update document status to completed
        await db.execute(
            "UPDATE documents SET status = 'completed' WHERE id = $1;",
            UUID(document_id),
        )

        # --- Stage 5: Done ---
        await job_manager.emit_event(
            job_id=job_id,
            stage="done",
            progress_percent=100,
            message=f"Successfully ingested {filename}: {total_pages} pages, {total_chunks} chunks stored with citations.",
            total_pages=total_pages,
            total_chunks=total_chunks,
        )
        logger.info(f"Document {document_id} ({filename}) ingested successfully.")

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error ingesting document {document_id}: {error_msg}", exc_info=True)
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
            message=f"Ingestion failed: {error_msg}",
            error=error_msg,
        )
