import json
import logging
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, status

from app.core.database import db
from app.models.document import (
    DocumentFullTextResponse,
    DocumentPageResponse,
    DocumentResponse,
)
from app.models.csv_table import (
    ColumnDefinition,
    CSVSchemaResponse,
    CSVPreviewResponse,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["documents"])


@router.get("/documents", response_model=List[DocumentResponse], summary="List uploaded documents")
async def list_documents(
    collection_id: Optional[str] = Query(None, description="Filter documents by collection UUID"),
) -> List[DocumentResponse]:
    """List documents with their upload status and chunk count."""
    params = []
    where_clause = ""
    if collection_id:
        try:
            params.append(UUID(collection_id))
            where_clause = "WHERE d.collection_id = $1"
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid collection UUID format.")

    query = f"""
    SELECT 
        d.id,
        d.collection_id,
        d.filename,
        d.type,
        d.status,
        d.total_pages,
        d.file_size,
        d.error,
        d.uploaded_at,
        COUNT(c.id)::int AS chunk_count
    FROM documents d
    LEFT JOIN chunks c ON c.document_id = d.id
    {where_clause}
    GROUP BY d.id
    ORDER BY d.uploaded_at DESC;
    """
    rows = await db.fetch_all(query, *params)
    return [
        DocumentResponse(
            id=str(r["id"]),
            collection_id=str(r["collection_id"]),
            filename=r["filename"],
            type=r["type"],
            status=r["status"],
            total_pages=r["total_pages"],
            file_size=r["file_size"],
            error=r.get("error"),
            uploaded_at=r["uploaded_at"],
            chunk_count=r["chunk_count"],
        )
        for r in rows
    ]


@router.get("/document/{document_id}/text", response_model=DocumentFullTextResponse, summary="Get full extracted text by page (PDF)")
async def get_document_full_text(document_id: str) -> DocumentFullTextResponse:
    """
    Section 3.5 Full-Text Rendering:
    Returns the complete page-by-page extracted text of an ingested PDF.
    """
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")

    doc = await db.fetch_one("SELECT id, filename, total_pages FROM documents WHERE id = $1;", doc_uuid)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")

    pages_query = """
    SELECT page_num, text
    FROM document_pages
    WHERE document_id = $1
    ORDER BY page_num ASC;
    """
    page_rows = await db.fetch_all(pages_query, doc_uuid)

    return DocumentFullTextResponse(
        document_id=str(doc["id"]),
        filename=doc["filename"],
        total_pages=doc["total_pages"],
        pages=[
            DocumentPageResponse(page_num=p["page_num"], text=p["text"])
            for p in page_rows
        ],
    )


@router.get("/document/{document_id}/csv-schema", response_model=CSVSchemaResponse, summary="Get CSV table schema definition")
async def get_csv_schema(document_id: str) -> CSVSchemaResponse:
    """
    Returns the dynamic PostgreSQL table name and inferred column definitions for a CSV document.
    Used by the query engine (PR #4) to generate exact SQL aggregations.
    """
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")

    row = await db.fetch_one(
        "SELECT document_id, collection_id, table_name, row_count, column_definitions, created_at FROM csv_tables WHERE document_id = $1;",
        doc_uuid,
    )
    if not row:
        raise HTTPException(status_code=404, detail="CSV table schema not found for this document.")

    col_defs_raw = row["column_definitions"]
    col_defs = (
        json.loads(col_defs_raw) if isinstance(col_defs_raw, str) else col_defs_raw
    )

    return CSVSchemaResponse(
        document_id=str(row["document_id"]),
        collection_id=str(row["collection_id"]),
        table_name=row["table_name"],
        row_count=row["row_count"],
        column_definitions=[ColumnDefinition(**c) for c in col_defs],
        created_at=row["created_at"],
    )


@router.get("/document/{document_id}/csv-preview", response_model=CSVPreviewResponse, summary="Preview raw rows from dynamic CSV table")
async def get_csv_preview(
    document_id: str,
    limit: int = Query(default=20, ge=1, le=100, description="Max rows to return for preview"),
) -> CSVPreviewResponse:
    """Preview the raw typed data rows stored in the dynamic PostgreSQL table."""
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")

    table_row = await db.fetch_one(
        "SELECT table_name, row_count, column_definitions FROM csv_tables WHERE document_id = $1;",
        doc_uuid,
    )
    if not table_row:
        raise HTTPException(status_code=404, detail="CSV table not found for this document.")

    table_name = table_row["table_name"]
    col_defs_raw = table_row["column_definitions"]
    col_defs = (
        json.loads(col_defs_raw) if isinstance(col_defs_raw, str) else col_defs_raw
    )
    col_names = [c["name"] for c in col_defs]

    # Query dynamic table for preview rows
    col_names_quoted = [f'"{name}"' for name in col_names]
    preview_query = f"""
    SELECT {', '.join(col_names_quoted)}
    FROM "{table_name}"
    ORDER BY _row_id ASC
    LIMIT $1;
    """
    rows = await db.fetch_all(preview_query, limit)

    return CSVPreviewResponse(
        document_id=str(doc_uuid),
        table_name=table_name,
        total_rows=table_row["row_count"],
        columns=col_names,
        rows=rows,
    )


@router.delete("/document/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete document")
async def delete_document(document_id: str):
    """Delete a document, cascade deleting pages/chunks and dropping any dynamic CSV table."""
    try:
        doc_uuid = UUID(document_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document UUID format.")

    # Check if there's a dynamic CSV table to drop
    csv_row = await db.fetch_one("SELECT table_name FROM csv_tables WHERE document_id = $1;", doc_uuid)
    if csv_row:
        table_name = csv_row["table_name"]
        try:
            await db.execute(f'DROP TABLE IF EXISTS "{table_name}";')
        except Exception as e:
            logger.warning(f"Error dropping CSV table {table_name}: {e}")

    deleted = await db.execute("DELETE FROM documents WHERE id = $1;", doc_uuid)
    if deleted == "DELETE 0":
        raise HTTPException(status_code=404, detail="Document not found.")
