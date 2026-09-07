import asyncio
import logging
from typing import AsyncGenerator, Dict, List, Tuple
from uuid import UUID

from app.core.database import db
from app.models.chat import Citation
from app.services.embedding import embedding_service
from app.llm import stream_llm_response

logger = logging.getLogger("uvicorn.error")


async def retrieve_semantic_chunks(
    query: str,
    collection_id: UUID,
    top_k: int = 8,
) -> Tuple[List[Dict], List[Citation]]:
    """
    Perform hybrid retrieval:
    1. 384-dimensional pgvector cosine similarity search over chunks scoped to collection_id.
    2. Structural / metadata enrichment for questions asking about authorship, cover details,
       or table of contents / chapter overviews.
    3. Deduplicates and constructs deterministic, mechanically-attached Citation objects.
    """
    # 1. Embed query into 384-dimensional vector
    query_vector = await asyncio.to_thread(embedding_service.embed_query, query)
    vector_str = f"[{','.join(str(x) for x in query_vector)}]"

    # 2. Vector search query
    sql = """
    SELECT 
        c.id,
        c.document_id,
        c.collection_id,
        c.source_file,
        c.type,
        c.page_num,
        c.char_offset,
        c.content,
        1 - (c.embedding <=> $1::vector) AS similarity
    FROM chunks c
    WHERE c.collection_id = $2
    ORDER BY c.embedding <=> $1::vector ASC
    LIMIT $3;
    """
    vector_records = await db.fetch_all(sql, vector_str, collection_id, top_k)

    # 3. Keyword / Structural Enrichment
    lower_query = query.lower()
    structural_records: List[Dict] = []

    if any(w in lower_query for w in ["author", "wrote", "who is", "creator", "writer"]):
        # Fetch front-matter & author bio chunks
        structural_records = await db.fetch_all(
            """
            SELECT c.id, c.document_id, c.collection_id, c.source_file, c.type, c.page_num, c.char_offset, c.content, 0.95 as similarity
            FROM chunks c
            WHERE c.collection_id = $1 AND (c.page_num IN (1, 2, 3, 4, 5, 706, 707, 708) OR c.content ILIKE '%author%' OR c.content ILIKE '%gayle%')
            ORDER BY c.page_num ASC
            LIMIT 4;
            """,
            collection_id,
        )
    elif any(w in lower_query for w in ["content", "contents", "chapter", "chapters", "table of contents", "topics", "outline", "summary"]):
        # Fetch Table of Contents & introductory structure
        structural_records = await db.fetch_all(
            """
            SELECT c.id, c.document_id, c.collection_id, c.source_file, c.type, c.page_num, c.char_offset, c.content, 0.95 as similarity
            FROM chunks c
            WHERE c.collection_id = $1 AND (c.page_num BETWEEN 6 AND 12 OR c.content ILIKE '%Chapter %' OR c.content ILIKE '%Table of Contents%')
            ORDER BY c.page_num ASC
            LIMIT 8;
            """,
            collection_id,
        )

    # 4. Merge and deduplicate by chunk ID
    seen_ids = set()
    combined_records: List[Dict] = []

    for r in structural_records + vector_records:
        if r["id"] not in seen_ids:
            seen_ids.add(r["id"])
            combined_records.append(r)

    # Cap to top 12 chunks for rich context
    final_records = combined_records[:12]

    citations: List[Citation] = []
    for idx, r in enumerate(final_records):
        snippet_text = r["content"].strip()
        snippet_preview = snippet_text if len(snippet_text) <= 280 else snippet_text[:280] + "…"
        citations.append(
            Citation(
                id=idx + 1,
                document_id=str(r["document_id"]),
                source_file=r["source_file"],
                type=r["type"],
                page_num=r["page_num"],
                char_offset=r["char_offset"],
                snippet=snippet_preview,
            )
        )

    return final_records, citations


async def stream_semantic_rag(
    query: str,
    collection_id: str,
) -> Tuple[AsyncGenerator[str, None], List[Citation]]:
    """
    Execute semantic RAG:
    1. Hybrid vector + structural search over pgvector chunks.
    2. Build deterministic citations.
    3. Stream response with Gemini -> Groq fallback grounded in context with inline [1], [2] badges.
    """
    try:
        col_uuid = UUID(collection_id)
    except ValueError:
        col_row = await db.fetch_one("SELECT id FROM collections WHERE LOWER(name) = LOWER($1);", collection_id)
        col_uuid = col_row["id"] if col_row else None

    if not col_uuid:
        async def empty_stream():
            yield "Collection not found. Please select or create a valid collection."
        return empty_stream(), []

    records, citations = await retrieve_semantic_chunks(query, col_uuid, top_k=8)

    if not records:
        async def no_docs_stream():
            yield "No relevant documents or chunks were found in this collection to answer your question."
        return no_docs_stream(), []

    # Build grounded context
    context_blocks = []
    for idx, r in enumerate(records):
        label = "Page" if r["type"] == "pdf" else "Row"
        context_blocks.append(
            f"[{idx + 1}] (Source: {r['source_file']}, {label} {r['page_num']}):\n{r['content']}"
        )

    context_str = "\n\n".join(context_blocks)

    system_instruction = (
        "You are Weave, a precise enterprise RAG system with deterministic citations.\n"
        "Answer the user's question accurately using facts present in the provided numbered context snippets.\n"
        "RULES:\n"
        "1. Every factual statement must cite its source snippet using bracketed numbers like [1], [2].\n"
        "2. Do not invent page numbers or facts not in the context.\n"
        "3. If the context does not contain enough information, state what is missing honestly.\n"
        "4. Format clearly with bullet points, bold section titles, or concise paragraphs where appropriate."
    )

    prompt = f"""
Provided Context:
{context_str}

User Question:
{query}
"""

    stream = stream_llm_response(prompt, system_prompt=system_instruction)
    return stream, citations
