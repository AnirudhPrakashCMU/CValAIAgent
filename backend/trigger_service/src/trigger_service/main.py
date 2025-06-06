import asyncio
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .config import settings
from .service import TriggerService

logger = logging.getLogger(settings.SERVICE_NAME)

service = TriggerService()


def create_app() -> FastAPI:
    app = FastAPI(
        title="MockPilot - Trigger Service",
        version="0.1.0",
        default_response_class=JSONResponse,
    )

    @app.on_event("startup")
    async def startup_event() -> None:
        app.state.runner = asyncio.create_task(service.run())

    @app.on_event("shutdown")
    async def shutdown_event() -> None:
        app.state.runner.cancel()
        try:
            await app.state.runner
        except asyncio.CancelledError:
            pass

    @app.get("/healthz")
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("trigger_service.main:app", host="0.0.0.0", port=8006, reload=True)
