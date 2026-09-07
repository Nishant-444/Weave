from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class DocumentBase(BaseModel):
    filename: str
    type: str = "pdf"
    collection_id: str


class DocumentCreate(DocumentBase):
    pass


class DocumentResponse(DocumentBase):
    id: str
    status: str
    total_pages: int = 0
    file_size: int = 0
    error: Optional[str] = None
    uploaded_at: datetime
    chunk_count: int = 0


class DocumentPageResponse(BaseModel):
    page_num: int
    text: str


class DocumentFullTextResponse(BaseModel):
    document_id: str
    filename: str
    total_pages: int
    pages: List[DocumentPageResponse]


class UploadResponse(BaseModel):
    document_id: str
    job_id: str
    filename: str
    collection_id: str
    status: str = "processing"
    message: str
