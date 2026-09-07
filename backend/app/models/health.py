from typing import Optional
from pydantic import BaseModel, Field


class DatabaseHealth(BaseModel):
    status: str = Field(..., description="'connected' or 'unreachable'")
    error: Optional[str] = Field(default=None, description="Error message if unreachable")


class HealthResponse(BaseModel):
    status: str = Field(..., description="Overall service status (e.g. 'ok')")
    environment: str = Field(..., description="Application environment ('development', 'production')")
    app_name: str = Field(..., description="Name of the application")
    database: DatabaseHealth = Field(..., description="Database connection health details")
    embedding_model: Optional[str] = Field(default=None, description="Embedding model background load status")
