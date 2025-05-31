import asyncio
import logging
from typing import AsyncGenerator, List, Optional, Tuple

import numpy as np
import torch

# Use a try-except block for robust import of settings and logger,
# allowing the module to be run standalone for testing if needed.
try:
    from ..config import settings  # Relative import for package use
except ImportError:
    # Fallback for direct execution or if the package structure context is different.
    # This assumes 'config.py' is in a 'speech_to_text' directory,
    # and this script is run from a context where 'speech_to_text' is discoverable.
    from speech_to_text.config import settings


logger = logging.getLogger(settings.SERVICE_NAME + ".vad")


class SileroVAD:
    """
    Handles Voice Activity Detection using the Silero VAD model.
    It processes audio chunks and yields segments of detected speech.
    """

    def __init__(self, config: Optional[type(settings)] = None):
        self.config = config if config else settings

        self.model = None
        self.utils = None  # To store Silero utility functions if needed
        self._load_model()  # Ensure model is loaded during initialization

        self.sample_rate = self.config.AUDIO_SAMPLE_RATE
        self.vad_threshold = self.config.VAD_THRESHOLD
        self.min_silence_duration_ms = self.config.VAD_MIN_SILENCE_DURATION_MS
        # self.speech_pad_ms = self.config.VAD_SPEECH_PAD_MS # Padding can be applied by STT service

        # VAD processes audio in fixed-size windows.
        self.window_size_samples = self.config.VAD_WINDOW_SIZE_SAMPLES

        # Internal state for stream processing
        self._audio_buffer = bytearray()
        self._is_speaking = False
        self._current_speech_frames: List[bytes] = []
        self._silence_counter_ms = 0.0  # Counts duration of silence *after* speech

        # Minimum duration for a speech segment to be considered valid (e.g., to filter out short noises)
        self.min_speech_duration_ms = 100  # ms

        logger.info(
            f"SileroVAD initialized. Sample Rate: {self.sample_rate}Hz, "
            f"Threshold: {self.vad_threshold}, Min Silence: {self.min_silence_duration_ms}ms, "
            f"VAD Window Samples: {self.window_size_samples}"
        )

    def _load_model(self):
        try:
            if self.config.AUDIO_SAMPLE_RATE not in [8000, 16000]:
                logger.warning(
                    f"Silero VAD officially supports 8kHz or 16kHz. Current sample rate is {self.config.AUDIO_SAMPLE_RATE}Hz. "
                    "Model performance may vary. Ensure your model variant supports this or resample audio if issues arise."
                )

            # PyTorch Hub might try to write to a default directory. If permissions are an issue:
            # torch.hub.set_dir('/path/to/writable/torch_hub_cache')
            self.model, self.utils = torch.hub.load(
                repo_or_dir=self.config.VAD_MODEL_REPO,
                model=self.config.VAD_MODEL_NAME,
                force_reload=False,  # Set to True if debugging model loading issues
                trust_repo=True,  # Required for newer PyTorch versions
            )
            # Example: (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = self.utils
            logger.info("Silero VAD model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}", exc_info=True)
            raise RuntimeError(f"Silero VAD model loading failed: {e}")

    def _bytes_to_tensor(self, audio_bytes: bytes) -> Optional[torch.Tensor]:
        """Converts raw audio bytes (PCM 16-bit mono) to a PyTorch tensor."""
        if not audio_bytes:
            return None
        try:
            # Ensure the byte string length is a multiple of 2 (for int16)
            if len(audio_bytes) % 2 != 0:
                logger.warning(f"Received audio_bytes with odd length {len(audio_bytes)}. Trimming last byte.")
                audio_bytes = audio_bytes[:-1]
            if not audio_bytes: # Check again after potential trim
                return None

            audio_int16 = np.frombuffer(audio_bytes, dtype=np.int16)
            audio_float32 = audio_int16.astype(np.float32) / 32767.0  # Normalize to [-1.0, 1.0]
            return torch.from_numpy(audio_float32)
        except Exception as e:
            logger.error(f"Error converting audio bytes to tensor: {e} (length: {len(audio_bytes)})", exc_info=True)
            return None

    def reset_states(self):
        """Resets the internal states for processing a new audio stream."""
        self._audio_buffer = bytearray()
        self._is_speaking = False
        self._current_speech_frames = []
        self._silence_counter_ms = 0.0
        logger.debug("SileroVAD states reset.")

    async def process_audio_stream(
        self, audio_byte_stream: AsyncGenerator[bytes, None]
    ) -> AsyncGenerator[Tuple[bytes, bool], None]:
        """
        Processes an asynchronous stream of audio byte chunks and yields speech segments.
        A speech segment is a continuous block of audio determined by VAD to contain speech,
        ending when a sufficient period of silence is detected.

        Args:
            audio_byte_stream: An async generator yielding raw audio byte chunks (PCM 16-bit mono).

        Yields:
            Tuple[bytes, bool]: A tuple containing:
                - speech_segment_bytes: The bytes of the detected speech segment.
                - is_final_segment: True if this segment is considered final because subsequent silence
                                    met the min_silence_duration_ms threshold.
        """
        self.reset_states()
        # Duration of one VAD processing window in milliseconds
        vad_window_duration_ms = (self.window_size_samples / self.sample_rate) * 1000.0

        async for incoming_chunk_bytes in audio_byte_stream:
            if not incoming_chunk_bytes: # Skip empty chunks
                continue
            self._audio_buffer.extend(incoming_chunk_bytes)

            # Process audio in VAD window sizes
            while len(self._audio_buffer) >= self.window_size_samples * 2:  # 2 bytes per sample for int16
                vad_processing_chunk_bytes = bytes(self._audio_buffer[:self.window_size_samples * 2])
                del self._audio_buffer[:self.window_size_samples * 2]

                vad_chunk_tensor = self._bytes_to_tensor(vad_processing_chunk_bytes)
                if vad_chunk_tensor is None:
                    logger.warning("Skipping VAD for invalid audio chunk tensor (None).")
                    continue

                try:
                    # Perform VAD inference
                    speech_prob = self.model(vad_chunk_tensor, self.sample_rate).item()
                except Exception as e:
                    logger.error(f"Error during VAD model inference: {e}", exc_info=True)
                    continue # Skip this chunk on error

                if speech_prob >= self.vad_threshold:  # Speech detected in current VAD window
                    if not self._is_speaking:
                        # Transition from silence to speech
                        logger.debug(f"Speech started (Prob: {speech_prob:.2f})")
                        self._is_speaking = True
                        # Start accumulating frames for a new speech segment
                        self._current_speech_frames = [vad_processing_chunk_bytes]
                    else:
                        # Continuing speech
                        self._current_speech_frames.append(vad_processing_chunk_bytes)
                    
                    self._silence_counter_ms = 0.0  # Reset silence counter as speech is active

                else:  # Silence detected in current VAD window
                    if self._is_speaking:
                        # Transition from speech to silence
                        # Append this first silence chunk to the current speech segment for context,
                        # as Whisper might benefit from a little trailing silence.
                        self._current_speech_frames.append(vad_processing_chunk_bytes)
                        self._silence_counter_ms += vad_window_duration_ms
                        
                        if self._silence_counter_ms >= self.min_silence_duration_ms:
                            # Sufficient silence detected after speech, finalize the current speech segment
                            if self._current_speech_frames:
                                speech_segment_bytes = b"".join(self._current_speech_frames)
                                segment_duration_ms = (len(speech_segment_bytes) / (self.sample_rate * 2)) * 1000.0
                                
                                if segment_duration_ms >= self.min_speech_duration_ms:
                                    logger.debug(
                                        f"Yielding FINAL speech segment after {self._silence_counter_ms:.0f}ms silence. "
                                        f"Segment duration: {segment_duration_ms:.0f}ms"
                                    )
                                    yield speech_segment_bytes, True  # True for is_final_segment
                                else:
                                    logger.debug(
                                        f"Dropping short speech segment ({segment_duration_ms:.0f}ms) after silence."
                                    )
                                
                                self._current_speech_frames = []  # Clear buffer for next segment
                                self._is_speaking = False  # Reset speaking state
                                self._silence_counter_ms = 0.0 # Reset silence counter
                    # else: still silence (not self._is_speaking), do nothing, wait for speech
                
                await asyncio.sleep(0) # Yield control to event loop periodically during heavy processing

        # End of audio_byte_stream, flush any remaining buffered speech
        if self._is_speaking and self._current_speech_frames:
            speech_segment_bytes = b"".join(self._current_speech_frames)
            segment_duration_ms = (len(speech_segment_bytes) / (self.sample_rate * 2)) * 1000.0

            if segment_duration_ms >= self.min_speech_duration_ms:
                logger.debug(
                    f"Flushing: Yielding FINAL speech segment at end of stream. Duration: {segment_duration_ms:.0f}ms"
                )
                yield speech_segment_bytes, True  # Consider this final
            else:
                logger.debug(
                    f"Flushing: Dropping short speech segment ({segment_duration_ms:.0f}ms) at end of stream."
                )
        
        self.reset_states() # Clean up states for potential reuse
        logger.info("VAD processing of audio stream completed.")


# --- Example Usage (for testing this module directly) ---
async def _test_audio_stream_producer(
    audio_data: bytes, client_chunk_size_bytes: int, delay_factor: float = 1.0
) -> AsyncGenerator[bytes, None]:
    """Simulates an async audio stream producer, yielding client-sized chunks."""
    for i in range(0, len(audio_data), client_chunk_size_bytes):
        chunk = audio_data[i : i + client_chunk_size_bytes]
        yield chunk
        # Simulate real-time delay based on client chunk duration
        chunk_duration_s = (len(chunk) / (settings.AUDIO_SAMPLE_RATE * 2)) # 2 bytes per sample for int16
        await asyncio.sleep(chunk_duration_s * delay_factor)


async def _main_vad_test():
    """Main function to test the SileroVAD class."""
    
    # Ensure logger level is appropriate for testing
    if settings.LOG_LEVEL == "INFO": # Temporarily elevate for test verbosity if needed
        logging.getLogger(settings.SERVICE_NAME).setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.info("Temporarily set VAD logger to DEBUG for test.")

    vad = SileroVAD()

    # Create dummy audio: 0.5s silence, 1.5s speech (sine wave), 0.5s silence
    sr = settings.AUDIO_SAMPLE_RATE
    bytes_per_sample = 2 # For int16 PCM

    silence_duration_s = 0.5
    speech_duration_s = 1.5
    
    silence_samples = int(sr * silence_duration_s)
    speech_samples = int(sr * speech_duration_s)
    
    silence_data = np.zeros(silence_samples, dtype=np.int16).tobytes()
    
    # Generate a sine wave for speech to make it somewhat realistic for VAD
    t = np.linspace(0, speech_duration_s, speech_samples, endpoint=False)
    speech_signal = (np.sin(2 * np.pi * 440 * t) * 0.3 * 32767).astype(np.int16) # Amplitude 0.3
    speech_data = speech_signal.tobytes()

    test_audio_full = silence_data + speech_data + silence_data + speech_data + silence_data # Two utterances
    
    # Client sends audio in small chunks, e.g., 50ms, as per ComponentImplementationGuide
    client_chunk_duration_ms = settings.AUDIO_INPUT_CHUNK_DURATION_MS
    client_chunk_samples = int(sr * (client_chunk_duration_ms / 1000.0))
    client_chunk_bytes = client_chunk_samples * bytes_per_sample

    logger.info(f"Starting VAD test with client chunks of {client_chunk_duration_ms}ms ({client_chunk_bytes} bytes).")
    logger.info(f"VAD processes in windows of {vad.window_size_samples} samples.")
    logger.info(f"Min silence for final segment: {vad.min_silence_duration_ms}ms.")
    logger.info(f"Min speech duration for segment: {vad.min_speech_duration_ms}ms.")


    segment_count = 0
    total_yielded_speech_duration_ms = 0
    async for speech_chunk_bytes, is_final in vad.process_audio_stream(
        _test_audio_stream_producer(test_audio_full, client_chunk_bytes, delay_factor=0.1) # Speed up simulation
    ):
        segment_count += 1
        duration_ms = (len(speech_chunk_bytes) / (sr * bytes_per_sample)) * 1000.0
        total_yielded_speech_duration_ms += duration_ms
        logger.info(
            f"Segment {segment_count}: Length={len(speech_chunk_bytes)} bytes ({duration_ms:.0f} ms), Final={is_final}"
        )
    
    expected_total_speech_s = speech_duration_s * 2 # Two speech utterances
    logger.info(f"VAD test completed. Total segments yielded: {segment_count}")
    logger.info(f"Expected total speech duration: {expected_total_speech_s * 1000:.0f} ms")
    logger.info(f"Actual total yielded speech duration: {total_yielded_speech_duration_ms:.0f} ms")


if __name__ == "__main__":
    # This allows running `python -m speech_to_text.utils.vad` from the `src` directory,
    # or `python vad.py` if run directly from `utils` (adjusting imports might be needed for latter).
    
    # Basic logging setup for standalone script execution
    default_log_level = logging.DEBUG # More verbose for testing
    logging.basicConfig(
        level=default_log_level,
        format="%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s"
    )
    # Ensure our module's logger also respects this level if it was set higher by default
    logger.setLevel(default_log_level)
    
    asyncio.run(_main_vad_test())
