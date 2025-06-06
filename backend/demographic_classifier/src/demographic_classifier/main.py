from fastapi import FastAPI
from fastapi.responses import JSONResponse

from .models import ClassifyRequest, TagList
from .service import classify_request
from .config import settings


def create_app() -> FastAPI:
    app = FastAPI(
        title="MockPilot - Demographic Classifier",
        version="0.1.0",
        default_response_class=JSONResponse,
    )

    @app.post("/classify", response_model=TagList)
    async def classify_endpoint(req: ClassifyRequest) -> TagList:
        return classify_request(req)

    @app.get("/healthz")
    async def health() -> dict:
        return {"status": "ok"}

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "demographic_classifier.main:app", host="0.0.0.0", port=8005, reload=True
    )
