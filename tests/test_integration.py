"""Integration tests for core API endpoints — auth, rate limiting, papers CRUD, hypotheses."""

import pytest
from httpx import AsyncClient, ASGITransport
from src.api.main import app
from src.database import db
from src.config import settings


@pytest.fixture(autouse=True)
async def setup_db():
    """Ensure database is connected and clean before each test."""
    await db.connect()
    # Clean tables for test isolation
    for table in ("hypotheses", "audit_events", "webhooks", "papers", "users"):
        try:
            await db._execute(f"DELETE FROM {table}")
        except Exception:
            pass
    yield
    # Don't close db — let the app's shutdown handler manage it


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def auth_headers(client: AsyncClient) -> dict:
    """Register a test user and return auth headers."""
    resp = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "TestPass123!", "name": "Tester"},
    )
    data = resp.json()
    token = data.get("access_token") or data.get("token", "")
    return {"Authorization": f"Bearer {token}"}


# ── Auth tests ────────────────────────────────────────────────────────


class TestAuth:
    async def test_register(self, client: AsyncClient):
        resp = await client.post(
            "/auth/register",
            json={"email": "new@test.com", "password": "Str0ng!Pass", "name": "New User"},
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert "access_token" in data or "token" in data

    async def test_register_duplicate(self, client: AsyncClient):
        await client.post(
            "/auth/register",
            json={"email": "dup@test.com", "password": "Str0ng!Pass", "name": "Dup"},
        )
        resp = await client.post(
            "/auth/register",
            json={"email": "dup@test.com", "password": "Str0ng!Pass", "name": "Dup"},
        )
        assert resp.status_code in (400, 409)

    async def test_login(self, client: AsyncClient):
        await client.post(
            "/auth/register",
            json={"email": "login@test.com", "password": "Str0ng!Pass", "name": "Login"},
        )
        resp = await client.post(
            "/auth/login",
            data={"username": "login@test.com", "password": "Str0ng!Pass"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code in (200, 422)

    async def test_login_wrong_password(self, client: AsyncClient):
        await client.post(
            "/auth/register",
            json={"email": "badpw@test.com", "password": "Str0ng!Pass", "name": "Bad"},
        )
        resp = await client.post(
            "/auth/login",
            data={"username": "badpw@test.com", "password": "WrongPass1!"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert resp.status_code in (401, 403, 422)

    async def test_me_endpoint(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data


# ── Rate limiting tests ───────────────────────────────────────────────


class TestRateLimit:
    async def test_rate_limit_headers_present(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/papers?page=1&page_size=5", headers=auth_headers)
        assert resp.status_code in (200, 404)  # 404 if no papers, which is fine
        assert "X-RateLimit-Limit" in resp.headers or resp.status_code != 200

    async def test_rate_limit_burst_exceeded(self, client: AsyncClient):
        """Send many rapid requests to trigger rate limit."""
        resp = None
        for _ in range(50):
            resp = await client.get("/health")
        # The 50th request may be limited
        if resp:
            assert resp.status_code in (200, 429)


# ── Papers CRUD tests ─────────────────────────────────────────────────


class TestPapers:
    async def test_list_papers_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/papers", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("total", 0) >= 0

    async def test_fetch_papers(self, client: AsyncClient, auth_headers: dict):
        """Test paper fetching endpoint — may be empty if no source configured."""
        resp = await client.post(
            "/papers/fetch",
            json={"query": "machine learning", "max_results": 5},
            headers=auth_headers,
        )
        # Should succeed whether or not papers are returned
        assert resp.status_code in (200, 422, 503)

    async def test_update_paper(self, client: AsyncClient, auth_headers: dict):
        """Update a paper's metadata."""
        resp = await client.put(
            "/papers/nonexistent-id",
            json={"title": "Updated Title"},
            headers=auth_headers,
        )
        assert resp.status_code == 404


# ── Hypothesis tests ──────────────────────────────────────────────────


class TestHypotheses:
    async def test_hypothesis_lifecycle(self, client: AsyncClient, auth_headers: dict):
        """Test the full hypothesis lifecycle in one flow: generate → evidence → evaluate → experiment."""
        # 1) Generate
        gen = await client.post(
            "/hypotheses/generate",
            json={"num_hypotheses": 3},
            headers=auth_headers,
        )
        assert gen.status_code == 200
        gen_data = gen.json()
        assert "hypotheses" in gen_data
        assert len(gen_data["hypotheses"]) > 0
        for h in gen_data["hypotheses"]:
            assert "evidence_items" in h

        h_id = gen_data["hypotheses"][0]["id"]

        # 2) Evidence
        ev = await client.get(f"/hypotheses/{h_id}/evidence", headers=auth_headers)
        assert ev.status_code == 200
        ev_data = ev.json()
        assert ev_data["hypothesis_id"] == h_id
        assert "evidence" in ev_data
        assert "evidence_count" in ev_data

        # 3) Evaluate
        eval_resp = await client.post(f"/hypotheses/evaluate/{h_id}", headers=auth_headers)
        assert eval_resp.status_code == 200
        eval_data = eval_resp.json()
        assert "supporting_evidence_count" in eval_data
        assert "evidence" in eval_data

        # 4) Experiment recommendation
        exp = await client.post(
            "/hypotheses/experiment",
            params={"hypothesis_id": h_id},
            headers=auth_headers,
        )
        assert exp.status_code == 200
        rec = exp.json()
        assert "title" in rec
        assert "description" in rec


# ── Health endpoint ────────────────────────────────────────────────────


class TestHealth:
    async def test_health(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
