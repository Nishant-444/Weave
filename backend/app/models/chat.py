from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="User question or query")
    collection_id: Optional[str] = Field(default="Default", description="Target collection UUID or name")
    history: Optional[List[ChatMessage]] = Field(default=None, description="Previous conversation messages for multi-turn context")


class Citation(BaseModel):
    id: int = Field(..., description="1-indexed citation number matching [1], [2] in the text response")
    document_id: str
    source_file: str
    type: Literal["pdf", "csv_row", "sql_query"]
    page_num: Optional[int] = Field(default=None, description="1-indexed page number for PDF or row number for CSV")
    char_offset: Optional[int] = Field(default=None, description="Character offset in source document")
    snippet: str = Field(..., description="Exact context snippet used for citation")
    sql_query: Optional[str] = Field(default=None, description="Executed SQL query if routed to SQL aggregation")


class RoutingDecision(BaseModel):
    route: Literal["semantic", "sql"]
    reason: str
    target_tables: List[str] = Field(default_factory=list)


class ChatStreamEvent(BaseModel):
    event: Literal["routing", "token", "citations", "error", "done"]
    data: Any
