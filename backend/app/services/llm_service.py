import asyncio
import json
import logging
import re
from typing import Any, AsyncGenerator, Dict, List, Optional
from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")
settings = get_settings()

GEMINI_MODEL = "gemini-3.6-flash"


class LLMService:
    """Service interacting with Google Gemini API for streaming generation and routing."""

    def __init__(self) -> None:
        self._client = None

    def _get_client(self):
        """Lazy load Google Gemini Client."""
        if self._client is None:
            api_key = settings.gemini_api_key.get_secret_value() if settings.gemini_api_key else ""
            if not api_key:
                raise ValueError("GEMINI_API_KEY is not configured in environment or .env.")
            from google import genai
            self._client = genai.Client(api_key=api_key)
        return self._client

    async def generate_text(self, prompt: str, system_instruction: Optional[str] = None) -> str:
        """Generate a complete text response from Gemini."""
        client = self._get_client()

        def _call():
            config = {}
            if system_instruction:
                config["system_instruction"] = system_instruction
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
                config=config if config else None,
            )
            return response.text or ""

        return await asyncio.to_thread(_call)

    async def stream_text(
        self, prompt: str, system_instruction: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """Stream response tokens from Gemini in real-time."""
        client = self._get_client()
        queue: asyncio.Queue = asyncio.Queue()

        def _producer():
            try:
                config = {}
                if system_instruction:
                    config["system_instruction"] = system_instruction
                response_stream = client.models.generate_content_stream(
                    model=GEMINI_MODEL,
                    contents=prompt,
                    config=config if config else None,
                )
                for chunk in response_stream:
                    if chunk.text:
                        queue.put_nowait(chunk.text)
                queue.put_nowait(None)  # Sentinel for completion
            except Exception as e:
                logger.error(f"Gemini streaming error: {e}")
                queue.put_nowait(e)

        # Run stream producer in worker thread
        asyncio.get_event_loop().run_in_executor(None, _producer)

        while True:
            item = await queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item


llm_service = LLMService()
