import asyncio
from typing import Optional
from fastapi import APIRouter, Request, Response, status
from app.core.config import get_settings
from app.core.database import db
from app.models.health import DatabaseHealth, HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse, summary="System & Database Health Check")
async def health_check(request: Request, response: Response) -> HealthResponse:
    """
    Health check endpoint:
    Verifies that FastAPI is running, loads configuration,
    checks database reachability and pgvector status, and verifies embedding model background loading.
    Returns HTTP 200 when healthy, or HTTP 503 Service Unavailable if any critical subsystem has failed.
    """
    settings = get_settings()
    db_health_dict = await db.check_health()
    db_health = DatabaseHealth(**db_health_dict)

    overall_status = "ok"
    embedding_model_status: Optional[str] = None

    task = getattr(request.app.state, "embedding_load_task", None)
    if task is not None:
        if task.done():
            try:
                if task.exception() is not None:
                    embedding_model_status = "failed"
                else:
                    embedding_model_status = "ready"
            except asyncio.CancelledError:
                embedding_model_status = "failed"
        else:
            embedding_model_status = "loading"

    # Propagatxe DB reachability failure to top-level status
    if db_health.status != "connected":
        overall_status = "failed"

    # Propagate embedding model failure to top-level status
    if embedding_model_status == "failed":
        overall_status = "failed"

    # Set HTTP 503 for automated monitors and load balancers if degraded/failed
    if overall_status == "failed":
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return HealthResponse(
        status=overall_status,
        environment=settings.app_env,
        app_name=settings.app_name,
        database=db_health,
        embedding_model=embedding_model_status,
    )
