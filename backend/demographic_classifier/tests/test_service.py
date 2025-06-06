import pytest
from httpx import AsyncClient

from demographic_classifier.main import app


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_classify_basic():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/classify", json={"text": "I love using React"})
    assert resp.status_code == 200
    tags = [t.title() for t in resp.json()["tags"]]
    assert "Frontend Dev" in tags
