import os
import pytest
from httpx import AsyncClient

os.environ.setdefault("OPENAI_API_KEY", "dummy")
from code_generator.main import app
from code_generator.models import DesignSpec

@pytest.mark.asyncio
async def test_generate_basic():
    spec = DesignSpec(component="button")
    import json
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.post("/v1/generate", json=json.loads(spec.model_dump_json()))
    assert resp.status_code == 200
    data = resp.json()
    assert "<button" in data["jsx"]
