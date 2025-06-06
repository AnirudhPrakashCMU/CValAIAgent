import os

import pytest
from httpx import AsyncClient

os.environ.setdefault("JWT_SECRET_KEY", "testsecret")
from orchestrator.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/v1/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_create_session():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/v1/sessions")
    assert resp.status_code == 201
    data = resp.json()
    assert "session_id" in data
    assert "token" in data
