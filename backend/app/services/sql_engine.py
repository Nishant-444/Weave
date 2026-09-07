import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Tuple
from uuid import UUID

from app.core.database import db
from app.models.chat import Citation
from app.llm import generate_llm_text, stream_llm_response

logger = logging.getLogger("uvicorn.error")


def sanitize_sql_query(raw_sql: str) -> str:
    """Extract clean SQL string, removing markdown code blocks and ensuring read-only."""
    cleaned = raw_sql.strip()
    cleaned = re.sub(r"^```(?:sql)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"```$", "", cleaned)
    cleaned = cleaned.strip()

    # Safety check: strictly read-only
    lower_sql = cleaned.lower()
    dangerous_keywords = ["drop ", "delete ", "insert ", "update ", "alter ", "truncate ", "create ", "grant ", "revoke "]
    for kw in dangerous_keywords:
        if kw in lower_sql:
            raise ValueError(f"Prohibited non-read-only keyword '{kw.strip()}' in generated SQL.")

    if not (lower_sql.startswith("select") or lower_sql.startswith("with")):
        raise ValueError("Generated query must begin with SELECT or WITH.")

    return cleaned


async def stream_sql_aggregation(
    query: str,
    collection_id: str,
) -> Tuple[AsyncGenerator[str, None], List[Citation]]:
    """
    Execute SQL Aggregation Path (PRD Section 3.3):
    1. Resolve CSV table schemas registered in active collection.
    2. Generate typed PostgreSQL SQL query with Gemini -> Groq fallback.
    3. Execute read-only query directly on PostgreSQL.
    4. Stream explanation using real computed numbers (no hallucinated math).
    5. Attach executed SQL query as deterministic citation.
    """
    try:
        col_uuid = UUID(collection_id)
    except ValueError:
        col_row = await db.fetch_one("SELECT id FROM collections WHERE LOWER(name) = LOWER($1);", collection_id)
        col_uuid = col_row["id"] if col_row else None

    if not col_uuid:
        async def empty_stream():
            yield "Collection not found. Please select a valid collection."
        return empty_stream(), []

    # 1. Fetch available CSV tables
    table_rows = await db.fetch_all(
        """
        SELECT 
            t.table_name,
            t.document_id,
            t.column_definitions,
            d.filename
        FROM csv_tables t
        JOIN documents d ON d.id = t.document_id
        WHERE t.collection_id = $1;
        """,
        col_uuid,
    )

    if not table_rows:
        async def no_tables_stream():
            yield "No CSV tables found in this collection for tabular SQL queries."
        return no_tables_stream(), []

    # 2. Build Schema context for Text-to-SQL
    schema_descriptions = []
    for r in table_rows:
        cols = r["column_definitions"]
        if isinstance(cols, str):
            cols = json.loads(cols)
        cols_text = "\n  ".join([
            f'"{c["name"]}" {c["data_type"]} -- Original CSV Header: "{c["original_name"]}"'
            for c in cols
        ])
        schema_descriptions.append(
            f'Table: "{r["table_name"]}" (Source file: {r["filename"]}):\n  {cols_text}'
        )

    all_schemas_str = "\n\n".join(schema_descriptions)

    # 3. Text-to-SQL generation prompt
    sql_prompt = f"""
You are a PostgreSQL expert writing accurate SQL queries for tabular data analysis.
Given the table schema(s) and user question, write a single valid PostgreSQL SELECT query to compute the answer.

Database Schemas:
{all_schemas_str}

RULES:
1. Output ONLY the raw SQL query. Do not wrap in markdown quotes.
2. Quote table names and column names properly (e.g. SELECT "company_name", AVG("total_revenue_m") FROM "csv_doc_...").
3. Use ROUND() for numeric calculations when appropriate (e.g. ROUND(AVG("total_revenue_m"), 2)).
4. Use standard aggregations: SUM, AVG, COUNT, MIN, MAX, GROUP BY, ORDER BY, LIMIT.
5. When filtering text/string columns (e.g., company names, regions, industry groups), ALWAYS use ILIKE '%<keyword>%' (e.g. "company_name" ILIKE '%Apex Systems%') to handle case variations and suffixes (Inc., Corp, Ltd.).
6. Only generate read-only SELECT queries.

User Question:
"{query}"
"""

    raw_sql = await generate_llm_text(sql_prompt)
    clean_sql = sanitize_sql_query(raw_sql)
    logger.info(f"Generated SQL for query '{query}':\n{clean_sql}")

    # 4. Execute SQL query on PostgreSQL
    sql_results: List[Dict[str, Any]] = []
    execution_error: str = ""
    try:
        sql_results = await db.fetch_all(clean_sql)
    except Exception as e:
        execution_error = str(e)
        logger.warning(f"Initial SQL execution error: {execution_error}. Attempting 1-shot repair...")

        # 1-shot repair attempt
        repair_prompt = f"""
The following PostgreSQL query produced an error:
Query:
{clean_sql}

Error:
{execution_error}

Database Schemas:
{all_schemas_str}

User Question:
"{query}"

Please output a corrected, working PostgreSQL SELECT query only.
"""
        try:
            repaired_sql_raw = await generate_llm_text(repair_prompt)
            clean_sql = sanitize_sql_query(repaired_sql_raw)
            sql_results = await db.fetch_all(clean_sql)
            execution_error = ""
        except Exception as retry_err:
            execution_error = str(retry_err)
            logger.error(f"SQL repair attempt also failed: {execution_error}")

    if execution_error:
        async def error_stream():
            yield f"I attempted to calculate the answer by executing a SQL query, but encountered an error:\n`{clean_sql}`\n\nError: {execution_error}"
        return error_stream(), []

    # 5. Build deterministic Citation
    source_file = table_rows[0]["filename"] if table_rows else "CSV Dataset"
    doc_id = str(table_rows[0]["document_id"]) if table_rows else ""
    formatted_results_json = json.dumps(sql_results[:50], default=str)

    citations = [
        Citation(
            id=1,
            document_id=doc_id,
            source_file=source_file,
            type="sql_query",
            page_num=None,
            char_offset=None,
            snippet=f"Computed from {len(sql_results)} matching row(s) in PostgreSQL table '{table_rows[0]['table_name']}'.",
            sql_query=clean_sql,
        )
    ]

    # 6. Stream formatted natural-language response with real computed numbers
    answer_prompt = f"""
You are Weave, a precise data analyst assistant.
The user asked a tabular aggregation question. We executed a real PostgreSQL query to compute exact mathematical results.

User Question:
"{query}"

Executed SQL Query:
```sql
{clean_sql}
```

Real Query Results ({len(sql_results)} rows):
{formatted_results_json}

INSTRUCTIONS:
1. Answer the user's question clearly and concisely using the EXACT numbers from the query results.
2. Present the data using clean markdown tables or bullet points where helpful.
3. Reference [1] as the verified SQL computation source.
4. Do not invent or alter any computed numbers.
"""

    stream = stream_llm_response(answer_prompt)
    return stream, citations
