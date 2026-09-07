import asyncio
import json
import logging
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from sse_starlette.sse import EventSourceResponse

from app.core.database import db
from app.models.document import UploadResponse
from app.services.job_manager import job_manager
from app.services.ingest_pipeline import process_pdf_document
from app.services.csv_ingest_pipeline import process_csv_document

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["ingest"])


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_202_ACCEPTED, summary="Upload PDF or CSV document for ingestion")
async def upload_document(
    file: UploadFile = File(..., description="PDF or CSV file to ingest"),
    collection_id: Optional[str] = Form(None, description="Target collection UUID or name (defaults to 'Default')"),
) -> UploadResponse:
    """
    Upload a PDF or CSV document.
    - PDF: Extracted per-page, chunked, and embedded into pgvector.
    - CSV (Dual Path): Loaded into a typed PostgreSQL table for SQL aggregations AND row-serialized into pgvector chunks.
    Initiates background ingestion pipeline and returns a job_id for live SSE tracking.
    """
    # 1. Validate file format
    filename = file.filename or "uploaded_file"
    lower_filename = filename.lower()
    is_pdf = lower_filename.endswith(".pdf")
    is_csv = lower_filename.endswith(".csv")

    if not (is_pdf or is_csv):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Please upload a .pdf or .csv document.",
        )

    doc_type = "pdf" if is_pdf else "csv"

    # Read file bytes
    file_bytes = await file.read()
    file_size = len(file_bytes)
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    # 2. Resolve collection_id
    target_col_id: Optional[UUID] = None
    if collection_id:
        try:
            target_col_id = UUID(collection_id)
            exists = await db.fetch_one("SELECT id FROM collections WHERE id = $1;", target_col_id)
            if not exists:
                target_col_id = None
        except ValueError:
            col_row = await db.fetch_one("SELECT id FROM collections WHERE LOWER(name) = LOWER($1);", collection_id)
            if col_row:
                target_col_id = col_row["id"]

    if not target_col_id:
        default_col = await db.fetch_one("SELECT id FROM collections WHERE name = 'Default';")
        if default_col:
            target_col_id = default_col["id"]
        else:
            new_col = await db.fetch_one(
                "INSERT INTO collections (name, description) VALUES ('Default', 'Default collection') RETURNING id;"
            )
            target_col_id = new_col["id"]

    # 3. Create document record in PostgreSQL
    query = """
    INSERT INTO documents (collection_id, filename, type, status, file_size)
    VALUES ($1, $2, $3, 'processing', $4)
    RETURNING id;
    """
    doc_row = await db.fetch_one(query, target_col_id, filename, doc_type, file_size)
    if not doc_row:
        raise HTTPException(status_code=500, detail="Failed to initialize document record in database.")

    doc_id_str = str(doc_row["id"])
    col_id_str = str(target_col_id)

    # 4. Create background job
    job_id = job_manager.create_job(document_id=doc_id_str)

    # 5. Launch asynchronous ingestion pipeline in background
    if is_pdf:
        asyncio.create_task(
            process_pdf_document(
                document_id=doc_id_str,
                collection_id=col_id_str,
                filename=filename,
                pdf_bytes=file_bytes,
                job_id=job_id,
            )
        )
    else:
        asyncio.create_task(
            process_csv_document(
                document_id=doc_id_str,
                collection_id=col_id_str,
                filename=filename,
                csv_bytes=file_bytes,
                job_id=job_id,
            )
        )

    return UploadResponse(
        document_id=doc_id_str,
        job_id=job_id,
        filename=filename,
        collection_id=col_id_str,
        status="processing",
        message=f"{doc_type.upper()} uploaded successfully. Ingestion pipeline running in background.",
    )


@router.get("/ingest/progress/{job_id}", summary="Stream ingestion progress via Server-Sent Events (SSE)")
async def stream_ingest_progress(job_id: str):
    """
    SSE stream emitting live stage events:
    `parsing` ➔ `chunking`/`storing` ➔ `embedding` ➔ `done` (or `failed`).
    """
    if job_id not in job_manager.jobs:
        raise HTTPException(status_code=404, detail="Ingestion job not found.")

    async def event_generator():
        async for event in job_manager.subscribe(job_id):
            yield {
                "event": "progress",
                "data": event.model_dump_json(),
            }
            if event.stage in ("done", "failed"):
                break

    return EventSourceResponse(event_generator())
