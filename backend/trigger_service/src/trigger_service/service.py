import json
import logging
import uuid

import redis.asyncio as aioredis
import httpx

from .config import settings
from .models import DesignSpec

logger = logging.getLogger(settings.SERVICE_NAME)

class TriggerService:
    def __init__(self) -> None:
        self.redis = aioredis.from_url(str(settings.REDIS_URL), decode_responses=False)
        self.in_chan = settings.REDIS_INTENTS_CHANNEL_NAME
        self.out_chan = settings.REDIS_DESIGN_SPECS_CHANNEL_NAME
        self.dm_url = settings.DESIGN_MAPPER_URL

    async def handle_intent(self, intent: dict) -> None:
        try:
            async with httpx.AsyncClient() as ac:
                resp = await ac.post(
                    f"{self.dm_url}/v1/map",
                    json={
                        "styles": intent.get("styles", []),
                        "brand_refs": intent.get("brand_refs", []),
                        "component": intent.get("component"),
                    },
                    timeout=5.0,
                )
                mapping = resp.json()
                tokens = mapping.get("theme_tokens", {})
        except Exception as e:
            logger.warning("Design mapper request failed: %s", e)
            tokens = {}

        spec = DesignSpec(
            component=intent["component"],
            theme_tokens=tokens,
            source_utts=[uuid.UUID(intent["utterance_id"])],
        )
        await self.redis.publish(self.out_chan, spec.model_dump_json())
        logger.info("Published DesignSpec %s", spec.spec_id)

    async def run(self) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.in_chan)
        logger.info("Subscribed to %s", self.in_chan)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                payload = json.loads(message["data"].decode())
                if payload.get("confidence", 1.0) >= settings.CONFIDENCE_THRESHOLD:
                    await self.handle_intent(payload)
            except Exception as e:
                logger.error("Failed to process intent: %s", e)
