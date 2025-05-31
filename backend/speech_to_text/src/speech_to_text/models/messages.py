from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


# --- Base Models ---
class AppBaseModel(BaseModel):
    """Base Pydantic model with common configuration."""

    model_config = {
        "frozen": True,  # Make models immutable by default
        "extra": "forbid",  # Disallow extra fields
    }


# --- Transcript Segment Models (for WebSocket communication) ---
class BaseTranscriptSegment(AppBaseModel):
    """
    Base model for a segment of a transcript.
    Common fields for both partial and final transcript updates over WebSocket.
    """

    text: str = Field(description="The transcribed text content of the segment.")
    ts_start: float = Field(
        description="Timestamp of the start of this segment in seconds from the beginning of the audio stream."
    )
    ts_end: float = Field(
        description="Timestamp of the end of this segment in seconds."
    )
    utterance_id: UUID = Field(
        default_factory=uuid4,
        description="Unique identifier for the continuous utterance this segment belongs to. "
        "Helps group related partials and the final transcript.",
    )
    speaker: Optional[str] = Field(
        default=None, description="Identifier for the speaker, if speaker diarization is active."
    )


class WebSocketTranscriptPartial(BaseTranscriptSegment):
    """
    Represents a partial (interim) transcript update sent over WebSocket.
    Corresponds to 'partial' type message in APIContracts.md.
    """

    type: Literal["partial"] = Field(
        default="partial", description="Indicates this is a partial transcript update."
    )


class WebSocketTranscriptFinal(BaseTranscriptSegment):
    """
    Represents a final transcript segment sent over WebSocket.
    Corresponds to 'final' type message in APIContracts.md.
    """

    type: Literal["final"] = Field(
        default="final", description="Indicates this is a final transcript segment."
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Overall confidence score for this final transcript segment (0.0 to 1.0).",
    )


# --- Redis Message Model (for publishing final transcripts) ---
class TranscriptMessage(AppBaseModel):
    """
    Model for a finalized transcript message to be published to Redis.
    This is what downstream services like Intent Extractor will consume.
    Aligns with 'TranscriptMsg' schema in APIContracts.md.
    """

    utterance_id: UUID = Field(
        description="Unique identifier for the transcribed utterance. "
        "This ID links back to WebSocketTranscript messages and is used for downstream processing."
    )
    text: str = Field(description="The fully transcribed text of the utterance.")
    ts_start: float = Field(
        description="Timestamp of the start of the utterance in seconds."
    )
    ts_end: float = Field(description="Timestamp of the end of the utterance in seconds.")
    speaker: Optional[str] = Field(
        default=None, description="Identifier for the speaker, if available."
    )
    confidence: Optional[float] = Field(
        default=None,
        description="Overall confidence score for the transcription (0.0 to 1.0).",
    )
    # is_final: Literal[True] = Field(default=True, description="Indicates this is a final transcript.") # Implicit by being a TranscriptMessage


# --- WebSocket Control Messages ---
class WebSocketControlMessage(AppBaseModel):
    """
    Model for control messages sent over WebSocket (e.g., for backpressure, errors, status).
    Example: {"type": "slow"} as per ComponentImplementationGuide.md.
    """

    type: Literal["slow", "error", "info", "status", "pong"] = Field(
        description="Type of the control message."
    )
    message: Optional[str] = Field(
        default=None, description="Optional descriptive message for 'error' or 'info' types."
    )
    data: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional additional data payload for the control message."
    )


# --- Union type for all possible outgoing WebSocket messages from STT service ---
WebSocketOutgoingMessage = Union[
    WebSocketTranscriptPartial, WebSocketTranscriptFinal, WebSocketControlMessage
]


# --- Incoming Audio Message (example, if structured messages are expected) ---
class WebSocketAudioChunk(AppBaseModel):
    """
    Represents an incoming audio chunk if sent as a structured JSON message.
    Typically, raw binary audio is preferred for efficiency.
    """
    type: Literal["audio_chunk"] = "audio_chunk"
    data: bytes = Field(description="Raw audio data bytes (e.g., 16-kHz mono PCM).")
    sequence_id: Optional[int] = Field(default=None, description="Optional sequence number for ordering.")
    timestamp_client: Optional[float] = Field(default=None, description="Optional client-side timestamp.")


if __name__ == "__main__":
    # Example usage for demonstration and schema export
    import json

    partial_example = WebSocketTranscriptPartial(
        text="Hello world this is a",
        ts_start=0.5,
        ts_end=2.1,
        speaker="Speaker1",
    )
    final_example = WebSocketTranscriptFinal(
        text="Hello world, this is a test.",
        ts_start=0.5,
        ts_end=3.0,
        utterance_id=partial_example.utterance_id, # Link to the same utterance
        speaker="Speaker1",
        confidence=0.92,
    )
    redis_msg_example = TranscriptMessage(
        utterance_id=final_example.utterance_id,
        text=final_example.text,
        ts_start=final_example.ts_start,
        ts_end=final_example.ts_end,
        speaker=final_example.speaker,
        confidence=final_example.confidence,
    )
    slow_control_msg = WebSocketControlMessage(type="slow")
    error_control_msg = WebSocketControlMessage(type="error", message="Processing failed.")

    print("--- WebSocketTranscriptPartial Example ---")
    print(json.dumps(partial_example.model_dump(), indent=2))
    print("\n--- WebSocketTranscriptFinal Example ---")
    print(json.dumps(final_example.model_dump(), indent=2))
    print("\n--- TranscriptMessage (for Redis) Example ---")
    print(json.dumps(redis_msg_example.model_dump(), indent=2))
    print("\n--- WebSocketControlMessage 'slow' Example ---")
    print(json.dumps(slow_control_msg.model_dump(), indent=2))
    print("\n--- WebSocketControlMessage 'error' Example ---")
    print(json.dumps(error_control_msg.model_dump(), indent=2))

    # print("\n--- WebSocketTranscriptPartial Schema ---")
    # print(json.dumps(WebSocketTranscriptPartial.model_json_schema(), indent=2))
    # print("\n--- TranscriptMessage Schema ---")
    # print(json.dumps(TranscriptMessage.model_json_schema(), indent=2))
