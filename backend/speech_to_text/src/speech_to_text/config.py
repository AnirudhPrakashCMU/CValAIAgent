import logging
from typing import Literal

from pydantic import Field, RedisDsn, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration settings for the Speech-to-Text service.
    Settings are loaded from environment variables and/or a .env file.
    """

    # --- General Service Settings ---
    SERVICE_NAME: str = "speech_to_text"
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = Field(
        default="INFO", description="Logging level for the service."
    )

    # --- OpenAI Whisper Settings ---
    OPENAI_API_KEY: SecretStr = Field(
        ..., description="API key for OpenAI services (Whisper)."
    )
    WHISPER_MODEL_NAME: str = Field(
        default="whisper-1",
        description="Name of the Whisper model to use (e.g., 'whisper-1' for API, or path for local).",
    )
    WHISPER_USE_LOCAL: bool = Field(
        default=False,
        description="If true, run Whisper locally instead of using the OpenAI API.",
    )
    # WHISPER_LANGUAGE: Optional[str] = Field(
    #     default=None, description="Optional language code for transcription (e.g., 'en')."
    # )
    WHISPER_PARTIAL_RESULT_INTERVAL_S: float = Field(
        default=0.4,
        description="Interval in seconds to send partial transcript updates. From guide: PARTIAL_INTERVAL = 0.4 s.",
    )
    WHISPER_MAX_BUFFERED_CHUNKS: int = Field(
        default=4,
        description="Maximum number of audio chunks to buffer for Whisper processing before applying backpressure. From guide: MAX_QUEUE = 4.",
    )

    # --- Redis Settings ---
    REDIS_URL: RedisDsn = Field(
        default="redis://localhost:6379/0",
        description="URL for the Redis server instance.",
    )
    REDIS_TRANSCRIPTS_CHANNEL_NAME: str = Field(
        default="transcripts",
        description="Redis channel name for publishing final transcript messages.",
    )
    REDIS_WEBSOCKET_BACKPRESSURE_CHANNEL_NAME: str = Field(
        default="ws_speech_backpressure",
        description="Redis channel name for publishing WebSocket backpressure signals (e.g., {'type':'slow'}).",
    )

    # --- Audio Input Settings ---
    AUDIO_SAMPLE_RATE: int = Field(
        default=16000, description="Sample rate for audio input in Hz. Whisper expects 16kHz."
    )
    AUDIO_CHANNELS: int = Field(
        default=1, description="Number of audio channels. Mono (1) is typical for STT."
    )
    AUDIO_INPUT_CHUNK_DURATION_MS: int = Field(
        default=50,
        description="Duration of audio chunks received from the client in milliseconds. From guide: Client sends 16-kHz mono PCM frames every ≤ 50 ms.",
    )
    # AUDIO_DEVICE_ID: Optional[int] = Field(
    #     default=None, description="Optional audio input device ID for sounddevice."
    # )

    # --- VAD (Voice Activity Detection) Settings - Silero VAD ---
    VAD_MODEL_REPO: str = Field(
        default="snakers4/silero-vad",
        description="Repository for the Silero VAD model on PyTorch Hub.",
    )
    VAD_MODEL_NAME: str = Field(
        default="silero_vad", description="Name of the Silero VAD model."
    )
    VAD_SAMPLING_RATE: int = Field(
        default=16000,
        description="Sampling rate expected by Silero VAD model (e.g., 8000 or 16000 Hz). Should match AUDIO_SAMPLE_RATE.",
    )
    VAD_THRESHOLD: float = Field(
        default=0.6,
        description="Sensitivity threshold for Silero VAD. Higher is more sensitive. From guide: SILERO_THRESHOLD = 0.6.",
    )
    VAD_MIN_SILENCE_DURATION_MS: int = Field(
        default=350,
        description="Minimum duration of silence in milliseconds to consider a speech segment final. From guide: on VAD silence ≥ 350 ms send final.",
    )
    VAD_SPEECH_PAD_MS: int = Field(
        default=100,
        description="Padding in milliseconds added to the start and end of detected speech segments.",
    )
    VAD_WINDOW_SIZE_SAMPLES: int = Field(
        default=512,
        description="Window size in samples for Silero VAD. Common values: 256, 512, 768, 1024, 1536 for 16kHz.",
    )

    # --- WebSocket Settings ---
    WEBSOCKET_MAX_SIZE_BYTES: int = Field(
        default=1024 * 1024 * 5,  # 5 MB
        description="Maximum size for incoming WebSocket messages in bytes.",
    )
    WEBSOCKET_PING_INTERVAL_S: float = Field(
        default=20.0, description="Interval in seconds for sending WebSocket ping frames."
    )
    WEBSOCKET_PING_TIMEOUT_S: float = Field(
        default=20.0, description="Timeout in seconds for WebSocket ping responses."
    )

    WEBSOCKET_RECEIVE_TIMEOUT_S: float = Field(
        default=5.0,
        description="Timeout in seconds waiting for audio bytes from the client WebSocket.",
    )

    model_config = SettingsConfigDict(
        env_file=".env",  # Load .env file if present
        env_file_encoding="utf-8",
        extra="ignore",  # Ignore extra environment variables
        case_sensitive=False, # Environment variables are typically case-insensitive
    )


# Initialize settings globally for easy access
# This instance will be populated when the module is imported.
settings = Settings()

# Configure logging based on settings
logging.basicConfig(
    level=settings.LOG_LEVEL.upper(),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(settings.SERVICE_NAME)

if __name__ == "__main__":
    # This block allows you to run this file directly to print out the loaded settings
    # Useful for debugging your configuration setup
    print("Loaded Speech-to-Text Service Settings:")
    for field_name, value in settings.model_dump().items():
        if isinstance(value, SecretStr):
            print(f"  {field_name}: {value.get_secret_value()[:4]}****") # Mask secrets
        else:
            print(f"  {field_name}: {value}")
