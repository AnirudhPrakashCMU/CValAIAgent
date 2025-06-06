import logging
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Path, status

from ..config import settings
from ..models.schemas import (
    AppBaseModel,
    SessionCreateResponse,
    SessionSummary,
    Token,
)
from ..utils import security

logger = logging.getLogger(settings.SERVICE_NAME + ".api_router")

# Using API_VERSION from settings to prefix routes for consistency.
# Example: /v1/healthz, /v1/sessions
router = APIRouter(prefix=f"/{settings.API_VERSION}")


# --- Health Check Endpoint ---
class HealthResponse(AppBaseModel):
    status: str = "ok"
    service_name: str = settings.SERVICE_NAME
    api_version: str = settings.API_VERSION
    current_time_utc: datetime


@router.get(
    "/healthz",
    tags=["Health"],
    summary="Perform a Health Check",
    response_model=HealthResponse,
)
async def health_check():
    """
    Simple health check endpoint.
    Returns a 200 OK response with service status and current time if the service is running.
    """
    logger.debug("Health check endpoint called.")
    return HealthResponse(current_time_utc=datetime.utcnow())


# --- Session Management Endpoints ---

# In a real application, session data might be stored in Redis or a database.
# For this hackathon, we might keep it simple or use Redis for session tracking.
# For now, session creation is very basic.
active_sessions: dict[UUID, SessionSummary] = {}  # In-memory store for demo purposes


@router.post(
    "/sessions",
    tags=["Session Management"],
    summary="Create a new client session",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_session():
    """
    Creates a new session identifier for a client.
    This session ID can then be used to connect to the WebSocket endpoint.
    """
    session_id = uuid4()
    now = datetime.utcnow()

    # Store basic session info (in-memory for now)
    active_sessions[session_id] = SessionSummary(
        session_id=session_id,
        created_at=now,
        last_activity_at=now,
        transcript_snippets=[],
        generated_components_count=0,
    )
    logger.info(f"New session created: {session_id}")

    access_token = security.create_access_token(
        {"sub": str(session_id), "scopes": ["session:active"]}
    )
    token_response = Token(access_token=access_token)
    return SessionCreateResponse(session_id=session_id, token=token_response)


@router.get(
    "/sessions/{session_id}/summary",
    tags=["Session Management"],
    summary="Get a summary of a specific session (Placeholder)",
    response_model=SessionSummary,
)
async def get_session_summary(
    session_id: UUID = Path(..., description="The unique identifier of the session.")
):
    """
    Retrieves a summary of the specified session.
    (Currently a placeholder, returns basic in-memory data if session exists).
    """
    logger.debug(f"Request for session summary: {session_id}")
    session_data = active_sessions.get(session_id)
    if not session_data:
        logger.warning(f"Session not found: {session_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session with ID '{session_id}' not found.",
        )

    # Update last activity (example)
    session_data.last_activity_at = datetime.utcnow()
    logger.info(f"Returning summary for session: {session_id}")
    return session_data


# TODO: Add more endpoints as needed, e.g.,
# - POST /sessions/{session_id}/action (e.g., trigger mockup generation manually)
# - DELETE /sessions/{session_id} (to explicitly end a session)

# Example of how this router would be included in the main FastAPI app:
# from .api import router as api_router_v1
# app.include_router(api_router_v1.router)
