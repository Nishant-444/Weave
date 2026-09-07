from typing import Optional, Literal
from pydantic import BaseModel, Field

JobStage = Literal["queued", "parsing", "chunking", "embedding", "storing", "done", "failed"]


class JobProgressEvent(BaseModel):
    job_id: str
    document_id: str
    stage: JobStage
    progress_percent: int = Field(..., ge=0, le=100)
    message: str
    total_pages: Optional[int] = None
    total_chunks: Optional[int] = None
    error: Optional[str] = None
