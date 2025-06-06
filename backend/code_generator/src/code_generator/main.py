import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .service import router

logger = logging.getLogger(settings.SERVICE_NAME)


def create_app() -> FastAPI:
    app = FastAPI(
        title="MockPilot - Code Generator Service",
        version="0.1.0",
        default_response_class=JSONResponse,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, tags=["Code Generator"])
    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("code_generator.main:app", host="0.0.0.0", port=8003, reload=True)
