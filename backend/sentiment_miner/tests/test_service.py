import json
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock

from sentiment_miner.main import app
from sentiment_miner.models import InsightMsg


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_handle_design_spec():
    payload = {
        "spec_id": "00000000-0000-0000-0000-000000000000",
        "component": "button",
    }
    # directly call handle_design_spec
    from sentiment_miner.service import handle_design_spec, settings, redis_client

    redis_client.publish = AsyncMock()
    await handle_design_spec(payload)
    redis_client.publish.assert_called_once()
    channel, data = redis_client.publish.call_args.args
    assert channel == settings.REDIS_INSIGHTS_CHANNEL_NAME
    msg = json.loads(data)
    assert msg["spec_id"] == payload["spec_id"]
    assert msg["posts"]
