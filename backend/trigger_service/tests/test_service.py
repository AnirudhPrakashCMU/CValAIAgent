import json
from unittest.mock import AsyncMock, Mock, patch
import pytest

from trigger_service.service import TriggerService
from trigger_service.config import settings


@pytest.mark.asyncio
async def test_handle_intent_publishes_spec():
    svc = TriggerService()
    svc.redis = AsyncMock()
    intent = {
        "utterance_id": "00000000-0000-0000-0000-000000000000",
        "component": "button",
        "styles": ["pill"],
        "brand_refs": ["stripe"],
        "confidence": 0.9,
    }
    mock_response = Mock()
    mock_response.json.return_value = {"theme_tokens": {"color": "blue"}}
    client = AsyncMock()
    client.post.return_value = mock_response
    cm = AsyncMock()
    cm.__aenter__.return_value = client
    cm.__aexit__.return_value = False
    with patch("httpx.AsyncClient", return_value=cm):
        await svc.handle_intent(intent)
    svc.redis.publish.assert_called_once()
    channel, payload = svc.redis.publish.call_args.args
    assert channel == settings.REDIS_DESIGN_SPECS_CHANNEL_NAME
    data = json.loads(payload)
    assert data["component"] == "button"
    assert data["theme_tokens"]["color"] == "blue"
