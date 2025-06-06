import json
import logging
import redis.asyncio as aioredis
from uuid import UUID

from .config import settings
from .models import InsightMsg, InsightPost

logger = logging.getLogger(settings.SERVICE_NAME)

redis_client = aioredis.from_url(str(settings.REDIS_URL), decode_responses=False)


async def handle_design_spec(message: dict) -> None:
    spec_id = UUID(message.get("spec_id"))
    query = message.get("component", "")
    # Dummy response: in a real service, query Weaviate and run sentiment model
    posts = [
        InsightPost(text="Looks great", sentiment=0.8, tags=["Gen Z"]),
        InsightPost(text="Not my style", sentiment=-0.5, tags=["Designer"]),
    ]
    insight = InsightMsg(spec_id=spec_id, query=query, posts=posts)
    await redis_client.publish(
        settings.REDIS_INSIGHTS_CHANNEL_NAME, insight.model_dump_json()
    )
    logger.info("Published insight for %s", spec_id)


async def run() -> None:
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(settings.REDIS_DESIGN_SPECS_CHANNEL_NAME)
    logger.info("Subscribed to %s", settings.REDIS_DESIGN_SPECS_CHANNEL_NAME)
    async for message in pubsub.listen():
        if message["type"] != "message":
            continue
        try:
            payload = json.loads(message["data"].decode())
            await handle_design_spec(payload)
        except Exception as e:
            logger.error("Failed to process design spec: %s", e)
