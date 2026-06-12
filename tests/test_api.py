import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport


@pytest.fixture
def mock_all_services():
    """Mock all external service dependencies."""
    with patch('src.memory.episodic.QdrantClient') as mock_qdrant, \
         patch('src.memory.semantic.GraphDatabase.driver') as mock_neo4j, \
         patch('src.services.embeddings.SentenceTransformer') as mock_st:

        mock_qdrant_instance = MagicMock()
        mock_qdrant_instance.get_collections.return_value = MagicMock(collections=[])
        mock_qdrant_instance.search = MagicMock(return_value=[])
        mock_qdrant_instance.scroll = MagicMock(return_value=([], None))
        mock_qdrant.return_value = mock_qdrant_instance

        mock_record = MagicMock()
        mock_record.__getitem__.side_effect = lambda k: 0

        mock_result = MagicMock()
        mock_result.single.return_value = mock_record

        mock_neo4j_instance = MagicMock()
        mock_session = MagicMock()
        mock_session.run.return_value = mock_result
        mock_session.__enter__.return_value = mock_session
        mock_neo4j_instance.session.return_value = mock_session
        mock_neo4j.return_value = mock_neo4j_instance

        mock_model = MagicMock()
        mock_model.encode.return_value = __import__('numpy').zeros(384)
        mock_st.return_value = mock_model

        yield


@pytest.fixture
async def client(mock_all_services):
    from src.api.main import app
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


class TestAPI:
    @pytest.mark.asyncio
    async def test_root(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "GSM-OS"
        assert data["status"] == "running"

    @pytest.mark.asyncio
    async def test_health(self, client):
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_search_similar_empty(self, client):
        response = await client.post(
            "/search/similar",
            params={"query": "test query", "limit": 5},
        )
        assert response.status_code == 200
        data = response.json()
        assert "results" in data

    @pytest.mark.asyncio
    async def test_memory_statistics(self, client):
        response = await client.get("/memory/statistics")
        assert response.status_code == 200
        data = response.json()
        assert "episodic" in data
        assert "semantic" in data

    @pytest.mark.asyncio
    async def test_graph_health(self, client):
        response = await client.get("/graph/health")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_hypothesis_generation(self, client):
        response = await client.post(
            "/hypotheses/generate",
            json={"num_hypotheses": 3},
        )
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_contradiction_summary(self, client):
        response = await client.get("/contradictions/summary")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_bottleneck_summary(self, client):
        response = await client.get("/bottlenecks/summary/Cancer")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_graph_missing_links(self, client):
        response = await client.get("/graph/missing-links")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_graph_clusters(self, client):
        response = await client.get("/graph/clusters/emerging")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_graph_visualize(self, client):
        response = await client.get("/graph/visualize/CRISPR", params={"depth": 2})
        assert response.status_code == 200
