import logging
from typing import List
from uuid import UUID
from fastapi import APIRouter, HTTPException, status

from app.core.database import db
from app.models.collection import CollectionCreate, CollectionResponse

logger = logging.getLogger("uvicorn.error")
router = APIRouter(prefix="/collections", tags=["collections"])


@router.get("", response_model=List[CollectionResponse], summary="List all collections")
async def list_collections() -> List[CollectionResponse]:
    """List all collections with their respective document count."""
    query = """
    SELECT 
        c.id, 
        c.name, 
        c.description, 
        c.created_at,
        COUNT(d.id)::int AS document_count
    FROM collections c
    LEFT JOIN documents d ON d.collection_id = c.id
    GROUP BY c.id
    ORDER BY c.created_at ASC;
    """
    rows = await db.fetch_all(query)
    return [
        CollectionResponse(
            id=str(row["id"]),
            name=row["name"],
            description=row.get("description"),
            created_at=row["created_at"],
            document_count=row["document_count"],
        )
        for row in rows
    ]


@router.post("", response_model=CollectionResponse, status_code=status.HTTP_201_CREATED, summary="Create a new collection")
async def create_collection(payload: CollectionCreate) -> CollectionResponse:
    """Create a new collection for multi-tenant isolation."""
    # Check if name already exists
    existing = await db.fetch_one("SELECT id FROM collections WHERE LOWER(name) = LOWER($1);", payload.name)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Collection '{payload.name}' already exists.",
        )

    query = """
    INSERT INTO collections (name, description)
    VALUES ($1, $2)
    RETURNING id, name, description, created_at;
    """
    row = await db.fetch_one(query, payload.name, payload.description)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create collection.")

    return CollectionResponse(
        id=str(row["id"]),
        name=row["name"],
        description=row.get("description"),
        created_at=row["created_at"],
        document_count=0,
    )


@router.get("/{collection_id}", response_model=CollectionResponse, summary="Get collection by ID")
async def get_collection(collection_id: str) -> CollectionResponse:
    """Get details of a specific collection."""
    try:
        col_uuid = UUID(collection_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid collection UUID format.")

    query = """
    SELECT 
        c.id, 
        c.name, 
        c.description, 
        c.created_at,
        COUNT(d.id)::int AS document_count
    FROM collections c
    LEFT JOIN documents d ON d.collection_id = c.id
    WHERE c.id = $1
    GROUP BY c.id;
    """
    row = await db.fetch_one(query, col_uuid)
    if not row:
        raise HTTPException(status_code=404, detail="Collection not found.")

    return CollectionResponse(
        id=str(row["id"]),
        name=row["name"],
        description=row.get("description"),
        created_at=row["created_at"],
        document_count=row["document_count"],
    )
