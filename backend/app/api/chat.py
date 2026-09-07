import json
import logging
from typing import AsyncGenerator
from fastapi import APIRouter, HTTPException, status
from sse_starlette.sse import EventSourceResponse

from app.models.chat import ChatRequest, RoutingDecision
from app.services.query_router import route_query
from app.services.semantic_engine import stream_semantic_rag
from app.services.sql_engine import stream_sql_aggregation

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["chat"])


@router.post("/chat", summary="Stream chat response with deterministic citations (SSE)")
async def chat_endpoint(payload: ChatRequest):
    """
    POST /chat (PRD Sections 3.2, 3.3, 4, 5):
    1. Query Router determines 'semantic' vs 'sql' path.
    2. 'semantic' path performs pgvector top-k retrieval + Gemini response with grounded citations.
    3. 'sql' path translates question to SQL against typed PostgreSQL tables + computes exact aggregations.
    4. Streams tokens, routing events, and final deterministic citation metadata via SSE.
    """
    collection_id = payload.collection_id or "Default"
    query = payload.query.strip()
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query cannot be empty.",
        )

    # 1. Routing classification
    routing_decision: RoutingDecision = await route_query(query, collection_id)
    logger.info(f"Query '{query}' routed to '{routing_decision.route}' ({routing_decision.reason})")

    async def sse_stream_generator():
        # Event 1: Emit routing decision
        yield {
            "event": "routing",
            "data": json.dumps({
                "route": routing_decision.route,
                "reason": routing_decision.reason,
            }),
        }

        # Select engine path
        if routing_decision.route == "sql":
            token_stream, citations = await stream_sql_aggregation(query, collection_id)
        else:
            token_stream, citations = await stream_semantic_rag(query, collection_id)

        # Event 2: Stream tokens as they arrive from LLM
        try:
            async for token in token_stream:
                yield {
                    "event": "token",
                    "data": json.dumps({"token": token}),
                }
        except Exception as e:
            logger.error(f"Error during LLM streaming: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }
            return

        # Event 3: Emit mechanically-attached citations
        yield {
            "event": "citations",
            "data": json.dumps({
                "citations": [c.model_dump() for c in citations]
            }),
        }

        # Event 4: Stream done
        yield {
            "event": "done",
            "data": json.dumps({
                "status": "completed",
                "route": routing_decision.route,
            }),
        }

    return EventSourceResponse(sse_stream_generator())
