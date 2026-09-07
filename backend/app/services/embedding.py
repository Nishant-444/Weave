import logging
from typing import List
import torch
from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")


class EmbeddingService:
    """Local batch embedding generator using sentence-transformers (all-MiniLM-L6-v2)."""

    def __init__(self) -> None:
        self._model = None

    def load_model(self):
        """Explicitly warm up / load the model into memory."""
        return self._get_model()

    def _get_model(self):
        """Lazy load SentenceTransformer model on CPU without meta-tensor dispatch."""
        if self._model is None:
            settings = get_settings()
            logger.info(f"Loading embedding model: {settings.embedding_model} on CPU...")
            from sentence_transformers import SentenceTransformer
            
            # Explicitly load directly onto CPU avoiding meta device copy issues on Python 3.14 / Torch 2.x
            try:
                self._model = SentenceTransformer(
                    settings.embedding_model,
                    device="cpu",
                    model_kwargs={"low_cpu_mem_usage": False},
                )
            except Exception:
                # Fallback for versions not accepting model_kwargs
                self._model = SentenceTransformer(
                    settings.embedding_model,
                    device="cpu",
                )
            
            logger.info(f"Embedding model {settings.embedding_model} loaded successfully.")
        return self._model

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """
        Batch embed a list of texts into normalized 384-dimensional float vectors.
        Fast and deterministic for 10k-scale document processing.
        """
        if not texts:
            return []

        model = self._get_model()
        # Encode with batching and normalization for cosine similarity search
        embeddings = model.encode(
            texts,
            batch_size=64,
            show_progress_bar=False,
            normalize_embeddings=True,
            device="cpu",
        )
        return [embedding.tolist() for embedding in embeddings]

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string."""
        return self.embed_texts([query])[0]


embedding_service = EmbeddingService()
