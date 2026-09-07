from datetime import datetime
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field


class CollectionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, description="Collection name")
    description: Optional[str] = Field(default=None, max_length=500, description="Collection description")


class CollectionCreate(CollectionBase):
    pass


class CollectionResponse(CollectionBase):
    id: str = Field(..., description="Unique collection UUID")
    created_at: datetime = Field(..., description="Creation timestamp")
    document_count: int = Field(default=0, description="Number of documents in this collection")
