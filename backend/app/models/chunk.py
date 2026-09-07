from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class ChunkBase(BaseModel):
    document_id: str
    collection_id: str
    source_file: str
    type: str = "pdf"
    page_num: int
    char_offset: int
    content: str


class ChunkCreate(ChunkBase):
    embedding: List[float] = Field(..., description="384-dimensional vector embedding")


class ChunkResponse(ChunkBase):
    id: str
    created_at: datetime
