import json
import logging
import re
from typing import Any, Dict, List, Optional
from uuid import UUID

from app.core.database import db
from app.models.chat import RoutingDecision
from app.llm import generate_llm_text

logger = logging.getLogger("uvicorn.error")

AGGREGATION_PATTERNS = [
    r"\baverage\b", r"\bavg\b", r"\btotal\b", r"\bsum\b", r"\bhow many\b",
    r"\bcount\b", r"\bhighest\b", r"\blowest\b", r"\bmax\b", r"\bmin\b",
    r"\btop\s+\d+\b", r"\bbottom\s+\d+\b", r"\bcompare\b", r"\bgreater than\b",
    r"\bless than\b", r"\bmore than\b", r"\bbetween\b", r"\bper\s+(quarter|year|company|region)\b",
    r"\bgrouped by\b", r"\bmedian\b", r"\branking\b", r"\brank\b", r"\bstandard deviation\b"
]


async def route_query(query: str, collection_id: str) -> RoutingDecision:
    """
    Classify user query into either 'semantic' or 'sql' route:
    - 'semantic': Vector similarity search over PDF text chunks and CSV rows.
    - 'sql': LLM-generated SQL query executed on dynamic PostgreSQL CSV tables for exact aggregations.
    """
    try:
        col_uuid = UUID(collection_id)
    except ValueError:
        col_row = await db.fetch_one("SELECT id FROM collections WHERE LOWER(name) = LOWER($1);", collection_id)
        col_uuid = col_row["id"] if col_row else None

    if not col_uuid:
        return RoutingDecision(route="semantic", reason="Collection not found; default to semantic search.")

    # 1. Fetch available CSV tables in this collection
    csv_table_rows = await db.fetch_all(
        "SELECT table_name, column_definitions FROM csv_tables WHERE collection_id = $1;",
        col_uuid,
    )

    # If no CSV tables exist in this collection, must be semantic search over PDFs
    if not csv_table_rows:
        return RoutingDecision(
            route="semantic",
            reason="No tabular CSV tables in collection; routing to semantic vector retrieval.",
            target_tables=[],
        )

    available_tables = [r["table_name"] for r in csv_table_rows]

    # 2. Rule-based heuristic check first
    lower_query = query.lower()
    has_agg_pattern = any(re.search(pat, lower_query) for pat in AGGREGATION_PATTERNS)

    # 3. LLM Router classification
    schemas_desc = []
    for r in csv_table_rows:
        cols = r["column_definitions"]
        if isinstance(cols, str):
            cols = json.loads(cols)
        col_names = [f"{c['name']} ({c['data_type']})" for c in cols]
        schemas_desc.append(f"Table '{r['table_name']}': columns [{', '.join(col_names)}]")

    router_prompt = f"""
You are a Query Router for a hybrid RAG system.
Given a user query and the available SQL database tables, determine if the question requires:
1. "sql": An exact mathematical calculation, tabular aggregation (SUM, AVG, COUNT, MAX, MIN, GROUP BY, ORDER BY, TOP N, WHERE filters) on the database.
2. "semantic": A descriptive, qualitative, conceptual, or text-based search.

Available Tabular Schemas:
{chr(10).join(schemas_desc)}

User Question: "{query}"

Respond with ONLY a raw JSON object (no markdown, no backticks) with this format:
{{
  "route": "sql" or "semantic",
  "reason": "short 1-sentence explanation",
  "target_tables": ["table_name_if_sql"]
}}
"""

    try:
        raw_classification = await generate_llm_text(router_prompt)
        # Clean potential markdown fences
        cleaned_json = raw_classification.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        parsed = json.loads(cleaned_json)
        route = parsed.get("route", "semantic").lower()
        if route in ("sql", "semantic"):
            return RoutingDecision(
                route=route,
                reason=parsed.get("reason", "Classified by LLM router."),
                target_tables=parsed.get("target_tables", available_tables if route == "sql" else []),
            )
    except Exception as e:
        logger.warning(f"LLM query routing failed ({e}); falling back to heuristic.")

    # Fallback to heuristic
    if has_agg_pattern:
        return RoutingDecision(
            route="sql",
            reason="Query contains aggregation keywords (average, total, max, etc.); routed to SQL engine.",
            target_tables=available_tables,
        )

    return RoutingDecision(
        route="semantic",
        reason="Query is descriptive; routed to semantic vector retrieval.",
        target_tables=[],
    )
