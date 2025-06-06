import logging
import json
from fastapi import APIRouter, HTTPException
from .models import DesignSpec, ComponentMsg
from .config import settings
import redis.asyncio as aioredis

logger = logging.getLogger(settings.SERVICE_NAME)
router = APIRouter()

redis_client = aioredis.from_url(str(settings.REDIS_URL), decode_responses=False)


def simple_generate(spec: DesignSpec) -> ComponentMsg:
    """Generate a trivial component based on spec without LLM."""
    if spec.component.lower() == "button":
        jsx = "<button class='px-4 py-2 bg-blue-500 text-white rounded'>Click</button>"
        named_exports = ["MockButton"]
    else:
        jsx = f"<div>{spec.component}</div>"
        named_exports = ["MockComponent"]
    return ComponentMsg(spec_id=spec.spec_id, jsx=jsx, named_exports=named_exports)


@router.post("/v1/generate", response_model=ComponentMsg)
async def generate_component(spec: DesignSpec):
    component = simple_generate(spec)
    try:
        await redis_client.publish(settings.REDIS_COMPONENTS_CHANNEL_NAME, component.model_dump_json())
    except Exception as e:
        logger.error("Redis publish failed: %s", e)
    return component
