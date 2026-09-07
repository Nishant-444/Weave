from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ColumnDefinition(BaseModel):
    name: str = Field(..., description="Sanitized SQL column identifier (e.g. 'total_revenue_m')")
    original_name: str = Field(..., description="Original raw CSV header (e.g. 'Total Revenue ($M)')")
    data_type: str = Field(..., description="PostgreSQL data type (e.g. 'NUMERIC', 'INTEGER', 'TEXT', 'TIMESTAMPTZ')")


class CSVSchemaResponse(BaseModel):
    document_id: str
    collection_id: str
    table_name: str
    row_count: int
    column_definitions: List[ColumnDefinition]
    created_at: datetime


class CSVPreviewResponse(BaseModel):
    document_id: str
    table_name: str
    total_rows: int
    columns: List[str]
    rows: List[Dict[str, Any]]
