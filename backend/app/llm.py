"""
LLM streaming layer with automatic provider fallback.

Both Gemini and Groq expose chat/streaming APIs, so this module wraps
them behind one function: `stream_llm_response`. Gemini is tried first
(config-driven, not hardcoded); if it fails *before yielding any tokens*
-- the normal shape of a 429 quota error -- we transparently retry the
same prompt on Groq instead.

Deliberately does NOT swap providers mid-stream: if Gemini dies after
already sending part of an answer, splicing in Groq's continuation
would risk a seam the user can't make sense of. Mid-stream failures are
raised instead, so the route layer can turn them into a clean "answer
interrupted, please retry" state for the frontend -- explicit failure
beats a silently glued-together answer.
"""
from collections.abc import AsyncIterator
import logging
from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")

# Both SDKs raise different exception classes for a quota error, but the
# message text reliably contains one of these. Matching on text instead
# of exception type keeps this working even if the SDKs change versions.
QUOTA_ERROR_MARKERS = ("429", "RESOURCE_EXHAUSTED", "rate limit", "quota", "exhausted")


def _looks_like_quota_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(marker.lower() in text for marker in QUOTA_ERROR_MARKERS)


async def _stream_gemini(prompt: str, system_prompt: str) -> AsyncIterator[str]:
    from google import genai

    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
    config = {"system_instruction": system_prompt} if system_prompt else None
    
    # Use native async client (client.aio) to prevent blocking the event loop
    stream = await client.aio.models.generate_content_stream(
        model=settings.gemini_model_name,
        contents=prompt,
        config=config,
    )
    async for chunk in stream:
        if chunk.text:
            yield chunk.text


async def _stream_groq(prompt: str, system_prompt: str) -> AsyncIterator[str]:
    from groq import AsyncGroq

    settings = get_settings()
    api_key = settings.groq_api_key.get_secret_value() if settings.groq_api_key else ""
    client = AsyncGroq(api_key=api_key)
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    stream = await client.chat.completions.create(
        model=settings.groq_model_name,
        messages=messages,
        stream=True,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta


async def stream_llm_response(prompt: str, system_prompt: str = "") -> AsyncIterator[str]:
    """Single entrypoint the /chat route calls. Tries Gemini; falls back
    to Groq automatically on a pre-stream quota failure."""
    settings = get_settings()
    tokens_yielded = False

    try:
        async for token in _stream_gemini(prompt, system_prompt):
            tokens_yielded = True
            yield token
        return  # Gemini completed the whole answer -- done.
    except Exception as exc:
        logger.warning(f"Gemini streaming attempt failed: {exc}")
        if tokens_yielded:
            raise  # mid-stream failure: surface it, don't patch over it
        if not settings.groq_api_key or not settings.groq_api_key.get_secret_value():
            logger.warning("No GROQ_API_KEY configured for fallback; re-raising.")
            raise  # no fallback configured -- nothing else to try
        if not _looks_like_quota_error(exc):
            raise  # a real bug shouldn't be masked as a "provider switch"

        logger.info(f"Failing over to Groq model: {settings.groq_model_name}")

    async for token in _stream_groq(prompt, system_prompt):
        yield token


async def generate_llm_text(prompt: str, system_prompt: str = "") -> str:
    """Non-streaming text generation with automatic Gemini -> Groq quota fallback."""
    settings = get_settings()
    try:
        from google import genai
        client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
        config = {"system_instruction": system_prompt} if system_prompt else None
        res = await client.aio.models.generate_content(
            model=settings.gemini_model_name,
            contents=prompt,
            config=config,
        )
        return res.text or ""
    except Exception as exc:
        logger.warning(f"Gemini text generation failed: {exc}")
        if not settings.groq_api_key or not settings.groq_api_key.get_secret_value() or not _looks_like_quota_error(exc):
            raise
        logger.info(f"Failing over text generation to Groq model: {settings.groq_model_name}")
        from groq import AsyncGroq
        client = AsyncGroq(api_key=settings.groq_api_key.get_secret_value())
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = await client.chat.completions.create(
            model=settings.groq_model_name,
            messages=messages,
        )
        return resp.choices[0].message.content or ""
