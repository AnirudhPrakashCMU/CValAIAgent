import asyncio
import io
import logging
import wave
from typing import Any, AsyncGenerator, Dict, List, Optional

import httpx

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI

# Use a try-except block for robust import of settings and logger,
# allowing the module to be run standalone for testing if needed.
try:
    from ..config import settings  # Relative import for package use
except ImportError:
    # Fallback for direct execution or if the package structure context is different.
    # This assumes 'config.py' is in a 'speech_to_text' directory,
    # and this script is run from a context where 'speech_to_text' is discoverable.
    from speech_to_text.config import settings


logger = logging.getLogger(settings.SERVICE_NAME + ".whisper_engine")


class WhisperEngine:
    """
    Handles speech-to-text transcription using the OpenAI Whisper API.
    It can process a stream of audio segments (typically from VAD) concurrently.
    """

    def __init__(self, config: Optional[type(settings)] = None):
        self.config = config if config else settings
        self.model_name = self.config.WHISPER_MODEL_NAME
        self.use_local = self.config.WHISPER_USE_LOCAL
        self.provider = self.config.STT_PROVIDER

        if self.use_local:
            try:
                import whisper  # type: ignore
            except Exception as e:
                logger.error(f"Local whisper requested but package not available: {e}")
                raise
            self.local_model = whisper.load_model(self.model_name)
            logger.info(f"WhisperEngine using local model: {self.model_name}")
        elif self.provider == "openai":
            if not self.config.OPENAI_API_KEY or not self.config.OPENAI_API_KEY.get_secret_value():
                logger.error("OpenAI API key is not configured.")
                raise ValueError("OPENAI_API_KEY must be set and not empty when not using local Whisper.")
            self.client = AsyncOpenAI(api_key=self.config.OPENAI_API_KEY.get_secret_value())
            logger.info(f"WhisperEngine using OpenAI API model: {self.model_name}")
        elif self.provider == "deepgram":
            if not self.config.DEEPGRAM_API_KEY or not self.config.DEEPGRAM_API_KEY.get_secret_value():
                logger.error("Deepgram API key is not configured.")
                raise ValueError("DEEPGRAM_API_KEY must be set when STT_PROVIDER=deepgram")
            logger.info("WhisperEngine using Deepgram API")
        else:
            raise ValueError(f"Unsupported STT_PROVIDER: {self.provider}")

        self.sample_rate = self.config.AUDIO_SAMPLE_RATE
        self.channels = self.config.AUDIO_CHANNELS  # Should be 1 for Whisper
        self.sample_width = 2  # 16-bit PCM = 2 bytes per sample

        # Max concurrent transcription tasks, aligns with "batches 4 chunks / GPU call"
        self.max_concurrent_tasks = self.config.WHISPER_MAX_BUFFERED_CHUNKS
        self.semaphore = asyncio.Semaphore(self.max_concurrent_tasks)

        logger.info(
            "WhisperEngine initialized. "
            f"Local: {self.use_local}, provider: {self.provider}, model: {self.model_name}, "
            f"max concurrent tasks: {self.max_concurrent_tasks}"
        )

    def _create_in_memory_wav(self, audio_bytes: bytes) -> io.BytesIO:
        """Creates an in-memory WAV file from raw PCM audio bytes."""
        wav_file = io.BytesIO()
        with wave.open(wav_file, "wb") as wf:
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.sample_width)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio_bytes)
        wav_file.seek(0)
        return wav_file

    async def transcribe_file_bytes(
        self, audio_bytes: bytes, language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribe a complete audio file provided as bytes."""
        if self.use_local:
            return await self._transcribe_single_segment_local(audio_bytes, language)
        if self.provider == "deepgram":
            return await self._transcribe_single_segment_deepgram(audio_bytes, language)
        return await self._transcribe_single_segment_api(audio_bytes, language)

    async def _transcribe_single_segment_api(
        self, audio_segment_bytes: bytes, language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribes a single audio segment using the OpenAI API."""
        if not audio_segment_bytes:
            logger.warning("Attempted to transcribe empty audio segment.")
            return None

        in_memory_wav = self._create_in_memory_wav(audio_segment_bytes)

        # The file needs a name for the API, even if it's an in-memory BytesIO object.
        file_tuple = ("audio.wav", in_memory_wav, "audio/wav")

        try:
            logger.debug(
                f"Sending segment of {len(audio_segment_bytes)} bytes to Whisper API. Language: {language or 'auto'}."
            )
            response = await self.client.audio.transcriptions.create(
                model=self.model_name,
                file=file_tuple,
                language=language,  # Pass language if specified
                response_format="verbose_json",
                timestamp_granularities=["segment", "word"],
            )
            logger.debug(f"Received transcription: {response.text[:50]}...")

            # Convert the Transcription object to a dictionary for easier downstream use (e.g., JSON serialization)
            # The Pydantic models from openai lib for segments/words are fine if consumers can handle them.
            # For simplicity here, we'll try to make them plain dicts/lists of dicts.
            
            def _convert_segments(segments_obj_list):
                if segments_obj_list is None: return None
                return [s.model_dump() for s in segments_obj_list]

            def _convert_words(words_obj_list):
                if words_obj_list is None: return None
                return [w.model_dump() for w in words_obj_list]

            result_dict = {
                "text": response.text,
                "language": response.language,
                "duration": response.duration,
                "segments": _convert_segments(response.segments),
                "words": _convert_words(response.words if hasattr(response, 'words') else None),
            }
            return result_dict

        except APIConnectionError as e:
            logger.error(f"Whisper API connection error: {e}")
        except APITimeoutError as e:
            logger.error(f"Whisper API request timed out: {e}")
        except APIError as e:
            logger.error(
                f"Whisper API error: Status {e.status_code}, Message: {e.message}, Type: {e.type}"
            )
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during transcription: {e}", exc_info=True
            )
        return None

    async def _transcribe_single_segment_local(
        self, audio_segment_bytes: bytes, language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribes a single audio segment using a local Whisper model."""
        if not audio_segment_bytes:
            logger.warning("Attempted to transcribe empty audio segment.")
            return None

        import tempfile

        in_memory_wav = self._create_in_memory_wav(audio_segment_bytes)
        with tempfile.NamedTemporaryFile(suffix=".wav") as tmp:
            tmp.write(in_memory_wav.read())
            tmp.flush()
            result = self.local_model.transcribe(
                tmp.name,
                language=language,
                word_timestamps=True,
                fp16=False,
            )

        return {
            "text": result.get("text", ""),
            "language": result.get("language"),
            "duration": result.get("duration"),
            "segments": result.get("segments"),
            "words": result.get("words"),
        }

    async def _transcribe_single_segment_deepgram(
        self, audio_segment_bytes: bytes, language: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Transcribes a single audio segment using Deepgram's API."""
        if not audio_segment_bytes:
            logger.warning("Attempted to transcribe empty audio segment.")
            return None

        if not self.config.DEEPGRAM_API_KEY:
            logger.error("Deepgram API key is not configured.")
            return None

        wav_bytes = self._create_in_memory_wav(audio_segment_bytes).getvalue()
        headers = {
            "Authorization": f"Token {self.config.DEEPGRAM_API_KEY.get_secret_value()}",
            "Content-Type": "audio/wav",
        }
        params = {"model": "nova"}
        if language:
            params["language"] = language

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(
                    "https://api.deepgram.com/v1/listen",
                    headers=headers,
                    params=params,
                    content=wav_bytes,
                )
                resp.raise_for_status()
                data = resp.json()
                text = (
                    data.get("results", {})
                    .get("channels", [{}])[0]
                    .get("alternatives", [{}])[0]
                    .get("transcript", "")
                )
                return {
                    "text": text,
                    "language": language,
                    "duration": data.get("duration"),
                    "segments": None,
                    "words": None,
                }
        except httpx.HTTPError as e:
            logger.error(f"Deepgram API error: {e}")
        except Exception as e:
            logger.error(
                f"Unexpected error during Deepgram transcription: {e}",
                exc_info=True,
            )
        return None

    async def transcribe_stream(
        self,
        vad_segment_provider: AsyncGenerator[bytes, None],
        language: Optional[str] = None,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Consumes an async generator of VAD speech segments, transcribes them
        concurrently up to `max_concurrent_tasks`, and yields transcription results.
        """

        async def _process_segment_with_semaphore(segment_bytes: bytes):
            async with self.semaphore:  # Acquire semaphore before starting task
                # Log semaphore state after acquisition
                logger.debug(
                    f"Semaphore acquired for segment of {len(segment_bytes)} bytes. "
                    f"Available slots: {self.semaphore._value}"
                )
                try:
                    if self.use_local:
                        return await self._transcribe_single_segment_local(
                            segment_bytes, language
                        )
                    elif self.provider == "deepgram":
                        return await self._transcribe_single_segment_deepgram(
                            segment_bytes, language
                        )
                    else:
                        return await self._transcribe_single_segment_api(
                            segment_bytes, language
                        )
                finally:
                    # Log semaphore state after release (implicitly handled by 'async with')
                    logger.debug(
                         f"Semaphore released for segment. Available slots after release: {self.semaphore._value}"
                    )


        active_tasks: List[asyncio.Task] = []
        try:
            async for segment_bytes in vad_segment_provider:
                if not segment_bytes:
                    logger.debug("Skipping empty segment from VAD provider.")
                    continue

                # Create a task for the current segment
                task = asyncio.create_task(
                    _process_segment_with_semaphore(segment_bytes)
                )
                active_tasks.append(task)

                # Eagerly process completed tasks if the list of active_tasks is large or for responsiveness
                # This loop ensures we yield results as soon as they are ready.
                if len(active_tasks) >= self.max_concurrent_tasks or self.semaphore._value == 0 : # Check if buffer is full or no semaphores free
                    done, pending = await asyncio.wait(
                        active_tasks, timeout=0.01, return_when=asyncio.FIRST_COMPLETED
                    )
                    for t in done:
                        result = await t  # Get result or raise exception
                        if result:
                            yield result
                    active_tasks = list(pending)
            
            # After the VAD provider is exhausted, wait for all remaining tasks to complete
            logger.debug(
                f"VAD stream ended. Waiting for {len(active_tasks)} remaining transcription tasks."
            )
            for task_to_complete in asyncio.as_completed(active_tasks):
                result = await task_to_complete
                if result:
                    yield result
            active_tasks.clear()

        except Exception as e:
            logger.error(
                f"Error in transcribe_stream processing loop: {e}", exc_info=True
            )
            # Cancel any outstanding tasks
            for task_to_cancel in active_tasks:
                if not task_to_cancel.done():
                    task_to_cancel.cancel()
            # Await cancellation (optional, but good practice)
            if active_tasks:
                await asyncio.gather(*active_tasks, return_exceptions=True)
        finally:
            logger.info("WhisperEngine transcribe_stream finished.")


# --- Example Usage (for testing this module directly) ---
async def _mock_vad_segment_provider(
    num_segments: int = 3, segment_duration_s: float = 1.5, sample_rate: int = 16000
) -> AsyncGenerator[bytes, None]:
    """Simulates a VAD segment provider yielding dummy audio data."""
    channels = 1  # Mono
    sample_width = 2  # 16-bit

    for i in range(num_segments):
        num_samples = int(sample_rate * segment_duration_s)
        # Create silent audio for simplicity in testing the pipeline
        # In a real scenario, this would be actual speech data from VAD
        dummy_audio_bytes = b"\x00\x00" * num_samples * channels
        logger.debug(
            f"MockVAD: Yielding segment {i + 1} of {len(dummy_audio_bytes)} bytes ({segment_duration_s}s)."
        )
        yield dummy_audio_bytes
        await asyncio.sleep(0.2)  # Simulate some delay between VAD segments


async def _main_whisper_engine_test():
    """Main function to test the WhisperEngine class."""
    global settings # Allow modification of the global settings instance after .env load

    if not settings.WHISPER_USE_LOCAL and (
        not settings.OPENAI_API_KEY
        or not settings.OPENAI_API_KEY.get_secret_value()
        or "your_openai_api_key_here" in settings.OPENAI_API_KEY.get_secret_value()
    ):
        logger.error(
            "OpenAI API key not set or is a placeholder. Please set a valid OPENAI_API_KEY in .env or environment."
        )
        print("OpenAI API key not set or invalid. Skipping WhisperEngine test.")
        return

    engine = WhisperEngine(config=settings) # Pass the potentially reloaded settings

    logger.info("Starting WhisperEngine test with mock VAD provider...")
    transcription_count = 0
    try:
        async for transcription_result in engine.transcribe_stream(
            _mock_vad_segment_provider(num_segments=2, segment_duration_s=2.0, sample_rate=settings.AUDIO_SAMPLE_RATE),
            language="en",  # Example: specify language
        ):
            transcription_count += 1
            logger.info(f"--- Received Transcription {transcription_count} ---")
            logger.info(f"  Text: {transcription_result['text']}")
            logger.info(f"  Duration: {transcription_result['duration']:.2f}s")
            logger.info(f"  Language: {transcription_result['language']}")
            if transcription_result.get("segments"):
                logger.info(
                    f"  Num Segments in API response: {len(transcription_result['segments'])}"
                )
                # logger.info(f"  First segment: {transcription_result['segments'][0]}")
            if transcription_result.get("words"):
                logger.info(
                    f"  Num Words in API response: {len(transcription_result['words'])}"
                )
                # logger.info(f"  First few words: {transcription_result['words'][:3]}")
            logger.info("--- End Transcription ---")

    except Exception as e:
        logger.error(f"Error during WhisperEngine test: {e}", exc_info=True)
    
    logger.info(
        f"WhisperEngine test completed. Transcribed {transcription_count} segments."
    )


if __name__ == "__main__":
    import os
    # Basic logging setup for standalone script execution
    # The global `settings` object from config.py already configures logging,
    # but we might want to ensure a default for direct script runs if config.py isn't fully set up.
    if not logging.getLogger().hasHandlers(): # Check if root logger is already configured
        logging.basicConfig(
            level=logging.DEBUG, # Default to DEBUG for testing this module
            format="%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s",
        )
    # Ensure our module's logger also respects this level if it was set higher by default
    logger.setLevel(logging.DEBUG)


    # Load .env file if this script is run directly
    # Path is ../../../../../.env from this file's location
    # (utils -> speech_to_text_pkg -> src -> speech_to_text_service_dir -> backend -> project_root)
    project_root_env = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".env")
    )
    
    if os.path.exists(project_root_env):
        load_dotenv(dotenv_path=project_root_env)
        logger.info(f".env file loaded from {project_root_env}")
        # Re-initialize settings to pick up .env vars if they weren't available at initial import
        # This is crucial for OPENAI_API_KEY
        settings = settings.__class__() # Re-instantiate using the existing class
        logger.info(
            f"Settings reloaded. OpenAI Key set: "
            f"{bool(settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.get_secret_value() and 'your_openai_api_key_here' not in settings.OPENAI_API_KEY.get_secret_value())}"
        )
        # Reconfigure logging if settings changed log level
        logging.getLogger().setLevel(settings.LOG_LEVEL.upper())
        logger.setLevel(settings.LOG_LEVEL.upper())


    else:
        logger.warning(
            f".env file not found at {project_root_env}. Relying on environment variables for OPENAI_API_KEY."
        )

    asyncio.run(_main_whisper_engine_test())
