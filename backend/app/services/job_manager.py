import asyncio
import logging
import uuid
from typing import AsyncGenerator, Dict, List, Optional
from app.models.job import JobProgressEvent, JobStage

logger = logging.getLogger("uvicorn.error")


class JobManager:
    """In-memory job progress tracking and Server-Sent Events (SSE) broadcaster."""

    def __init__(self) -> None:
        self.jobs: Dict[str, JobProgressEvent] = {}
        self.subscribers: Dict[str, List[asyncio.Queue]] = {}

    def create_job(self, document_id: str) -> str:
        """Initialize a new ingestion job in 'queued' state."""
        job_id = str(uuid.uuid4())
        initial_event = JobProgressEvent(
            job_id=job_id,
            document_id=document_id,
            stage="queued",
            progress_percent=0,
            message="Ingestion job queued.",
        )
        self.jobs[job_id] = initial_event
        self.subscribers[job_id] = []
        return job_id

    async def emit_event(
        self,
        job_id: str,
        stage: JobStage,
        progress_percent: int,
        message: str,
        total_pages: Optional[int] = None,
        total_chunks: Optional[int] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update job state and broadcast progress event to all active SSE subscribers."""
        if job_id not in self.jobs:
            return

        doc_id = self.jobs[job_id].document_id
        event = JobProgressEvent(
            job_id=job_id,
            document_id=doc_id,
            stage=stage,
            progress_percent=progress_percent,
            message=message,
            total_pages=total_pages,
            total_chunks=total_chunks,
            error=error,
        )
        self.jobs[job_id] = event

        # Notify active queues
        if job_id in self.subscribers:
            for queue in self.subscribers[job_id]:
                await queue.put(event)

    async def subscribe(self, job_id: str) -> AsyncGenerator[JobProgressEvent, None]:
        """Subscribe to live progress stream for a specific job."""
        queue: asyncio.Queue = asyncio.Queue()

        if job_id not in self.subscribers:
            self.subscribers[job_id] = []
        self.subscribers[job_id].append(queue)

        # Immediately send the latest known state
        if job_id in self.jobs:
            yield self.jobs[job_id]

        try:
            while True:
                event = await queue.get()
                yield event
                if event.stage in ("done", "failed"):
                    break
        finally:
            if job_id in self.subscribers and queue in self.subscribers[job_id]:
                self.subscribers[job_id].remove(queue)


job_manager = JobManager()
