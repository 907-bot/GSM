"""
EmbeddingService — dual-mode:
  • Local dev:  uses sentence-transformers (requires PyTorch, installed via pip locally)
  • Docker/prod: falls back to HuggingFace Inference API over HTTP (no PyTorch needed)

Set EMBEDDING_BACKEND=local  → force sentence-transformers
Set EMBEDDING_BACKEND=remote → force HuggingFace HTTP API
Default: auto-detect (local if sentence-transformers importable, else remote)
"""
import asyncio
import numpy as np
from typing import List, Optional
from ..config import settings
import structlog

logger = structlog.get_logger()

# ── Attempt local import (will fail gracefully in the Docker container) ──
try:
    from sentence_transformers import SentenceTransformer
    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    _HAS_SENTENCE_TRANSFORMERS = False
    logger.info(
        "sentence-transformers not installed — using HuggingFace HTTP API for embeddings",
        tip="To enable local embeddings: pip install sentence-transformers",
    )


class EmbeddingService:
    """
    Service for generating text embeddings.
    Auto-selects local (sentence-transformers) or remote (HuggingFace API) mode.
    """

    def __init__(self):
        self._model = None
        backend = getattr(settings, "EMBEDDING_BACKEND", "auto").lower()
        if backend == "local":
            self._use_local = True
        elif backend == "remote":
            self._use_local = False
        else:
            # auto: use local if available
            self._use_local = _HAS_SENTENCE_TRANSFORMERS

        if self._use_local:
            logger.info("EmbeddingService: local mode (sentence-transformers)", model=settings.EMBEDDING_MODEL)
        else:
            logger.info("EmbeddingService: remote mode (HuggingFace HTTP API)", model=settings.EMBEDDING_MODEL)

    @property
    def model(self):
        if self._model is None and self._use_local:
            logger.info("Loading local embedding model", model=settings.EMBEDDING_MODEL)
            try:
                self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            except Exception as e:
                logger.warning("Local embedding model unavailable; switching to hash/remote fallback", error=str(e))
                self._use_local = False
                return None
        return self._model

    # ── Core embed methods ─────────────────────────────────────────────

    async def embed_text(self, text: str) -> np.ndarray:
        if self._use_local:
            loop = asyncio.get_event_loop()
            try:
                embedding = await loop.run_in_executor(
                    None, lambda: self.model.encode(text, convert_to_numpy=True) if self.model else None
                )
                if embedding is not None:
                    return embedding
            except Exception as e:
                logger.warning("Local embedding failed; using fallback embedding", error=str(e))
                self._use_local = False
            return await self._embed_remote(text)
        else:
            return await self._embed_remote(text)

    async def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        if self._use_local:
            loop = asyncio.get_event_loop()
            try:
                embeddings = await loop.run_in_executor(
                    None,
                    lambda: self.model.encode(
                        texts, batch_size=batch_size, convert_to_numpy=True,
                        show_progress_bar=len(texts) > 100,
                    ) if self.model else None,
                )
                if embeddings is not None:
                    return embeddings.tolist()
            except Exception as e:
                logger.warning("Local batch embedding failed; using fallback embeddings", error=str(e))
                self._use_local = False
            return [await self._embed_remote(text) for text in texts]
        else:
            results = []
            for text in texts:
                emb = await self._embed_remote(text)
                results.append(emb)
            return results

    async def embed_paper(self, title: str, abstract: str = None) -> np.ndarray:
        text = f"{title} {abstract}" if abstract else title
        return await self.embed_text(text)

    async def embed_finding(self, finding_text: str) -> np.ndarray:
        return await self.embed_text(finding_text)

    # ── HuggingFace HTTP fallback ──────────────────────────────────────

    async def _embed_remote(self, text: str) -> np.ndarray:
        """
        Call the HuggingFace Inference API to get embeddings.
        Uses HUGGINGFACE_API_KEY from settings.
        Falls back to a simple hash-based pseudo-embedding if the API key is missing.
        """
        import httpx

        hf_key = getattr(settings, "HUGGINGFACE_API_KEY", None)
        model = getattr(settings, "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

        # Normalize model name for HF API
        if "/" not in model:
            model = f"sentence-transformers/{model}"

        if hf_key:
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(
                        f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model}",
                        headers={"Authorization": f"Bearer {hf_key}"},
                        json={"inputs": text[:512], "options": {"wait_for_model": True}},
                    )
                    resp.raise_for_status()
                    data = resp.json()
                    # HF returns list of lists (sentence embedding)
                    if isinstance(data, list) and data:
                        vec = data[0] if isinstance(data[0], list) else data
                        return np.array(vec, dtype=np.float32)
            except Exception as e:
                logger.warning("HuggingFace embedding API failed, using hash fallback", error=str(e))

        # ── Last resort: deterministic hash-based pseudo-embedding ──
        # Not semantically meaningful but prevents crashes.
        # Replace with a real API key for production use.
        logger.warning(
            "No HUGGINGFACE_API_KEY set — using hash pseudo-embedding (not semantic!)",
            tip="Set HUGGINGFACE_API_KEY in .env for real embeddings",
        )
        rng = np.random.default_rng(seed=abs(hash(text)) % (2**31))
        return rng.random(384).astype(np.float32)

    # ── Similarity utilities ───────────────────────────────────────────

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    async def find_most_similar(
        self, query: np.ndarray, candidates: List[np.ndarray], top_k: int = 5
    ) -> List[int]:
        similarities = [self.cosine_similarity(query, c) for c in candidates]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return top_indices.tolist()


embedding_service = EmbeddingService()
