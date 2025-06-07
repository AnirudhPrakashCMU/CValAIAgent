import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import settings
from . import service

logger = logging.getLogger(settings.SERVICE_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title="MockPilot - Sentiment Miner",
        version="0.1.0",
        default_response_class=JSONResponse,
    )

    @app.on_event("startup")
    async def startup() -> None:
        app.state.runner = asyncio.create_task(service.run())

    @app.on_event("shutdown")
    async def shutdown() -> None:
        app.state.runner.cancel()
        try:
            await app.state.runner
        except asyncio.CancelledError:
            pass

    @app.get("/healthz")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("sentiment_miner.main:app", host="0.0.0.0", port=8004, reload=True)
