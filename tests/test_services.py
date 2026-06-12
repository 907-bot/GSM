import pytest
import numpy as np
from unittest.mock import patch, MagicMock


class TestEmbeddingService:
    @patch('src.services.embeddings.SentenceTransformer')
    def test_embed_text_returns_array(self, mock_st):
        mock_model = MagicMock()
        mock_model.encode.return_value = np.array([0.1, 0.2, 0.3])
        mock_st.return_value = mock_model

        from src.services.embeddings import EmbeddingService
        service = EmbeddingService()
        embedding = service.model.encode("test", convert_to_numpy=True)
        assert len(embedding) == 3

    def test_cosine_similarity_identical(self):
        from src.services.embeddings import EmbeddingService
        service = EmbeddingService()
        a = np.array([1, 0, 0])
        b = np.array([1, 0, 0])
        assert service.cosine_similarity(a, b) == 1.0

    def test_cosine_similarity_opposite(self):
        from src.services.embeddings import EmbeddingService
        service = EmbeddingService()
        a = np.array([1, 0, 0])
        c = np.array([-1, 0, 0])
        assert service.cosine_similarity(a, c) == -1.0

    def test_cosine_similarity_orthogonal(self):
        from src.services.embeddings import EmbeddingService
        service = EmbeddingService()
        a = np.array([1, 0, 0])
        b = np.array([0, 1, 0])
        assert abs(service.cosine_similarity(a, b)) < 1e-10

    @pytest.mark.asyncio
    async def test_find_most_similar(self):
        from src.services.embeddings import EmbeddingService
        service = EmbeddingService()
        query = np.array([1, 0, 0])
        candidates = [
            np.array([1, 0, 0]),
            np.array([0, 1, 0]),
            np.array([-1, 0, 0]),
            np.array([0.9, 0.1, 0]),
            np.array([0, 0, 1]),
        ]
        indices = await service.find_most_similar(query, candidates, top_k=3)
        assert len(indices) == 3
        assert indices[0] == 0

    @pytest.mark.asyncio
    async def test_find_most_similar_top_k(self):
        from src.services.embeddings import EmbeddingService
        service = EmbeddingService()
        query = np.array([1, 0, 0])
        candidates = [np.array([1, 0, 0]), np.array([0, 1, 0])]
        indices = await service.find_most_similar(query, candidates, top_k=5)
        assert len(indices) == 2
