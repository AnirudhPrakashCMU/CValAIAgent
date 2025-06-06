import asyncio
import json
import logging
import redis.asyncio as aioredis

from .config import settings
from .models import IntentMsg
from .regex_rules import detect

logger = logging.getLogger(settings.SERVICE_NAME)

class IntentExtractor:
    def __init__(self) -> None:
        self.redis = aioredis.from_url(str(settings.REDIS_URL), decode_responses=False)
        self.in_chan = settings.REDIS_TRANSCRIPTS_CHANNEL_NAME
        self.out_chan = settings.REDIS_INTENTS_CHANNEL_NAME

    async def run(self) -> None:
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(self.in_chan)
        logger.info("Subscribed to %s", self.in_chan)
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                payload = json.loads(message["data"].decode())
                text = payload.get("text", "")
                utterance_id = payload.get("utterance_id")
                speaker = payload.get("speaker")
                res = detect(text)
                if res:
                    intent = IntentMsg(
                        utterance_id=utterance_id,
                        component=res["component"],
                        styles=res["styles"],
                        brand_refs=res["brand_refs"],
                        speaker=speaker,
                    )
                    await self.redis.publish(self.out_chan, intent.model_dump_json())
                    logger.info("Published intent for %s", utterance_id)
            except Exception as e:
                logger.error("Failed to process message: %s", e)

async def main() -> None:
    extractor = IntentExtractor()
    await extractor.run()

if __name__ == "__main__":
    asyncio.run(main())
