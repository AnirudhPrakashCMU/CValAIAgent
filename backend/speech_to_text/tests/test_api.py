import os
import pytest
from httpx import AsyncClient

os.environ.setdefault("OPENAI_API_KEY", "dummy")
from speech_to_text.main import app

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
