from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Optional
from ..config import settings
import structlog

logger = structlog.get_logger()


class EmbeddingService:
    """Service for generating embeddings using sentence-transformers."""

    def __init__(self):
        self._model: Optional[SentenceTransformer] = None

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info("Loading embedding model", model=settings.EMBEDDING_MODEL)
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
        return self._model

    async def embed_text(self, text: str) -> np.ndarray:
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding

    async def embed_texts(self, texts: List[str], batch_size: int = 32) -> List[np.ndarray]:
        embeddings = self.model.encode(
            texts, batch_size=batch_size, convert_to_numpy=True,
            show_progress_bar=len(texts) > 100,
        )
        return embeddings.tolist()

    async def embed_paper(self, title: str, abstract: str = None) -> np.ndarray:
        text = title
        if abstract:
            text = f"{title} {abstract}"
        return await self.embed_text(text)

    async def embed_finding(self, finding_text: str) -> np.ndarray:
        return await self.embed_text(finding_text)

    def cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))

    async def find_most_similar(
        self, query: np.ndarray, candidates: List[np.ndarray], top_k: int = 5
    ) -> List[int]:
        similarities = [self.cosine_similarity(query, c) for c in candidates]
        top_indices = np.argsort(similarities)[-top_k:][::-1]
        return top_indices.tolist()


embedding_service = EmbeddingService()
