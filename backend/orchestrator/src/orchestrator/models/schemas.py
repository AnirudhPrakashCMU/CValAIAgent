from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl


# --- Base Pydantic Model ---
class AppBaseModel(BaseModel):
    """Base Pydantic model with common configuration."""

    model_config = {
        "frozen": False, # Allow modification for some use cases if needed, but generally good to be frozen
        "extra": "forbid",
        "populate_by_name": True, # Allows using alias for field names if defined
    }


# --- JWT Token Models ---
class Token(AppBaseModel):
    """Response model for JWT access token."""
    access_token: str
    token_type: Literal["bearer"] = "bearer"


class TokenPayload(AppBaseModel):
    """Model for the data encoded within a JWT."""
    sub: str  # Subject (e.g., user_id or session_id)
    exp: Optional[datetime] = None # Expiration time
    scopes: List[str] = []


# --- Session Management Models ---
class SessionCreateResponse(AppBaseModel):
    """Response model for creating a new session."""
    session_id: UUID = Field(default_factory=uuid4)
    message: str = "Session created successfully."
    # May include token if session creation also implies login
    # token: Optional[Token] = None


class SessionSummary(AppBaseModel):
    """Model for representing a summary of a session (placeholder)."""
    session_id: UUID
    created_at: datetime
    last_activity_at: datetime
    transcript_snippets: List[str] = Field(default_factory=list)
    generated_components_count: int = 0


# --- Relayed Data Structure Models (from APIContracts.md) ---
# These models represent the core data objects passed through the system.
# They are published by various services to Redis and relayed by the Orchestrator.

class TranscriptMsgPayload(AppBaseModel):
    """Payload for a transcript message, as published to Redis and relayed."""
    msg_id: UUID = Field(default_factory=uuid4, description="Unique ID for this specific transcript message/segment.")
    utterance_id: UUID = Field(description="ID for the continuous utterance this segment belongs to.")
    text: str
    ts_start: float = Field(description="Timestamp of the start of this segment in seconds, relative to utterance start.")
    ts_end: float = Field(description="Timestamp of the end of this segment in seconds, relative to utterance start.")
    speaker: Optional[str] = None
    confidence: Optional[float] = None


class IntentMsgPayload(AppBaseModel):
    """Payload for an intent message."""
    utterance_id: UUID
    component: str
    styles: List[str] = Field(default_factory=list)
    brand_refs: List[str] = Field(default_factory=list)
    confidence: float
    speaker: Optional[str] = None


class DesignSpecPayload(AppBaseModel):
    """Payload for a design specification message."""
    spec_id: UUID = Field(default_factory=uuid4)
    component: str
    theme_tokens: Dict[str, Any] = Field(default_factory=dict)
    interaction: Optional[str] = None
    source_utts: List[UUID] = Field(default_factory=list, description="List of utterance_ids that contributed to this spec.")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ComponentMsgPayload(AppBaseModel):
    """Payload for a generated component message."""
    spec_id: UUID
    jsx: str
    tailwind: bool
    named_exports: List[str] = Field(default_factory=list)
    lint_passed: bool
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class SocialPostPreview(AppBaseModel):
    """Represents a preview of a social media post for sentiment insights."""
    post_id: str
    text: str
    sentiment: float # e.g., -1.0 to 1.0
    url: Optional[HttpUrl] = None
    source: Optional[Literal["reddit", "instagram", "twitter"]] = None


class InsightMsgPayload(AppBaseModel):
    """Payload for a sentiment/demographic insight message."""
    spec_id: UUID
    sentiment_histogram: Dict[Literal["positive", "neutral", "negative"], int]
    demographic_breakdown: Dict[str, Dict[Literal["positive", "neutral", "negative"], int]] # e.g. {"Gen Z": {"positive": 10, ...}}
    top_posts: List[SocialPostPreview] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


# --- WebSocket Message Models (Server -> Client) ---
# These models are what the Orchestrator sends to connected WebSocket clients.
# Each includes a 'kind' field to differentiate message types.

class WSTranscriptMessage(TranscriptMsgPayload):
    """WebSocket message carrying a transcript segment."""
    kind: Literal["transcript"] = "transcript"


class WSIntentMessage(IntentMsgPayload):
    """WebSocket message carrying a detected design intent."""
    kind: Literal["intent"] = "intent"


class WSComponentMessage(ComponentMsgPayload):
    """WebSocket message carrying a generated UI component."""
    kind: Literal["component"] = "component"


class WSInsightMessage(InsightMsgPayload):
    """WebSocket message carrying sentiment and demographic insights."""
    kind: Literal["insight"] = "insight"


class WSErrorMessage(AppBaseModel):
    """WebSocket message for broadcasting errors to the client."""
    kind: Literal["error"] = "error"
    message: str
    detail: Optional[str] = None
    error_code: Optional[str] = None # e.g., "SERVICE_UNAVAILABLE", "VALIDATION_ERROR"


class WSServiceStatusMessage(AppBaseModel):
    """WebSocket message for broadcasting service status updates (e.g., service down/up)."""
    kind: Literal["service_status"] = "service_status" # Changed from "service_down" to be more general
    service_name: str
    status: Literal["up", "down", "degraded"]
    message: Optional[str] = None


# Union type for all possible outgoing WebSocket messages from Orchestrator
OrchestratorWebSocketOutgoingMessage = Union[
    WSTranscriptMessage,
    WSIntentMessage,
    WSComponentMessage,
    WSInsightMessage,
    WSErrorMessage,
    WSServiceStatusMessage,
]


# --- WebSocket Message Models (Client -> Server) ---
# These models represent messages the Orchestrator might receive from clients.

class ClientAudioChunkMessage(AppBaseModel):
    """
    Represents an audio chunk sent from client to orchestrator.
    Note: As per ComponentImplementationGuide, audio might go directly to STT service.
    This model is here if Orchestrator needs to handle/proxy it.
    """
    kind: Literal["audio_chunk"] = "audio_chunk"
    session_id: UUID
    data_b64: str # Base64 encoded audio data
    sequence_id: Optional[int] = None # For ordering
    timestamp_client: Optional[float] = None # Client-side timestamp


class ClientEditComponentMessage(AppBaseModel):
    """Represents a client request to edit a component (e.g., manual code changes)."""
    kind: Literal["edit_component"] = "edit_component"
    session_id: UUID
    spec_id: UUID # ID of the component/spec being edited
    patch_type: Literal["full_code", "diff"] = "full_code"
    code: str # Full new code or diff patch


class ClientControlMessage(AppBaseModel):
    """Generic client control messages, e.g., to start/stop aspects of a session."""
    kind: Literal["control_session"] = "control_session"
    session_id: UUID
    action: Literal["start_listening", "stop_listening", "request_mockup_now"]
    params: Optional[Dict[str, Any]] = None


# Union type for all possible incoming WebSocket messages to Orchestrator
OrchestratorWebSocketIncomingMessage = Union[
    ClientAudioChunkMessage,
    ClientEditComponentMessage,
    ClientControlMessage,
]


if __name__ == "__main__":
    # Example usage for demonstration and schema export
    import json

    print("--- Example: WSTranscriptMessage ---")
    ws_transcript_example = WSTranscriptMessage(
        msg_id=uuid4(),
        utterance_id=uuid4(),
        text="This is a live transcript update.",
        ts_start=10.5,
        ts_end=12.3,
        speaker="User1"
    )
    print(json.dumps(ws_transcript_example.model_dump(exclude_none=True), indent=2))

    print("\n--- Example: WSComponentMessage ---")
    ws_component_example = WSComponentMessage(
        spec_id=uuid4(),
        jsx="<button>Click Me</button>",
        tailwind=True,
        named_exports=["MyButton"],
        lint_passed=True,
        generated_at=datetime.utcnow()
    )
    # Pydantic v2 uses model_dump_json for direct JSON string
    print(ws_component_example.model_dump_json(indent=2, exclude_none=True))


    print("\n--- Example: WSErrorMessage ---")
    ws_error_example = WSErrorMessage(
        message="Failed to generate component.",
        detail="Underlying LLM service returned an error.",
        error_code="CODEGEN_LLM_FAILURE"
    )
    print(ws_error_example.model_dump_json(indent=2, exclude_none=True))

    print("\n--- Example: ClientEditComponentMessage ---")
    client_edit_example = ClientEditComponentMessage(
        session_id=uuid4(),
        spec_id=uuid4(),
        code="<button>Updated Button</button>"
    )
    print(client_edit_example.model_dump_json(indent=2, exclude_none=True))

    # print("\n--- Schema: OrchestratorWebSocketOutgoingMessage (OneOf) ---")
    # This would typically be part of an OpenAPI schema generation process.
    # Pydantic can generate JSON schemas for individual models.
    # For Union types, the schema would represent a oneOf/anyOf structure.
    # print(json.dumps(WSTranscriptMessage.model_json_schema(), indent=2))
