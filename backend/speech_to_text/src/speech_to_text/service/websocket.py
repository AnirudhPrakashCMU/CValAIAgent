import asyncio
import logging
import uuid  # For utterance IDs
import math # For confidence score conversion if needed

from fastapi import APIRouter, Path, WebSocket, WebSocketDisconnect
from starlette import status as http_status # For WebSocket close codes

# Assuming these are structured as per previous files
from ..config import settings
from ..models.messages import (
    TranscriptMessage,
    WebSocketControlMessage,
    WebSocketTranscriptFinal,
    WebSocketTranscriptPartial,
)
from ..utils.publisher import RedisPublisher
from ..utils.vad import SileroVAD
from ..utils.whisper_engine import WhisperEngine

logger = logging.getLogger(settings.SERVICE_NAME + ".websocket")

router = APIRouter()

# A simple connection manager for logging or potential future use.
class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket, client_id_str: str):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket client {client_id_str} connected. Total active: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket, client_id_str: str):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket client {client_id_str} disconnected. Total active: {len(self.active_connections)}")

manager = ConnectionManager()


@router.websocket("/v1/stream/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Path(..., min_length=1, description="Unique identifier for the meeting or session."),
):
    """
    WebSocket endpoint for streaming audio for speech-to-text.
    - Receives audio chunks from the client.
    - Processes audio through VAD to detect speech segments.
    - Transcribes speech segments using Whisper.
    - Sends partial and final transcript messages back to the client.
    - Publishes final transcripts to Redis.
    """
    client_id_str = f"{websocket.client.host}:{websocket.client.port}" if websocket.client else f"unknownclient-{uuid.uuid4()}"
    await manager.connect(websocket, client_id_str)

    vad_processor = SileroVAD(config=settings)
    whisper_processor = WhisperEngine(config=settings)
    redis_publisher = RedisPublisher(config=settings)
    
    pipeline_task: asyncio.Task | None = None

    try:
        if not await redis_publisher.connect():
            logger.error(f"[{client_id_str}] Failed to connect to Redis for session {session_id}. Closing WebSocket.")
            await websocket.send_text(
                WebSocketControlMessage(type="error", message="Internal server error: Service unavailable.").model_dump_json()
            )
            # Using a standard close code, 1011 indicates server error
            await websocket.close(code=http_status.WS_1011_INTERNAL_ERROR)
            return

        logger.info(f"[{client_id_str}] Initialized VAD, Whisper, and Redis for session: {session_id}")

        # This async generator yields raw audio byte chunks from the WebSocket client.
        async def audio_bytes_from_websocket_producer():
            try:
                while True:
                    # TODO: Consider adding a timeout for websocket.receive_bytes()
                    # to handle cases where client stops sending data without disconnecting.
                    audio_data = await websocket.receive_bytes()
                    if not audio_data: # Should not happen with receive_bytes unless client sends empty binary frame
                        logger.debug(f"[{client_id_str}] Received empty audio data packet, skipping.")
                        continue
                    logger.debug(f"[{client_id_str}] Received {len(audio_data)} audio bytes from WebSocket.")
                    yield audio_data
            except WebSocketDisconnect:
                logger.info(f"[{client_id_str}] Client disconnected while sending audio (handled by producer).")
                raise # Propagate to the main handler to terminate the pipeline
            except Exception as e_ws_recv:
                logger.error(f"[{client_id_str}] Error receiving audio bytes: {e_ws_recv}", exc_info=True)
                raise # Propagate

        # Event to signal when VAD has marked the end of an utterance.
        vad_marked_utterance_as_final_event = asyncio.Event()

        # Adapter: Consumes (speech_bytes, is_final_utterance_flag) from VAD,
        # yields speech_bytes to Whisper, and sets the event if is_final_utterance_flag is true.
        async def vad_speech_adapter_for_whisper(vad_results_stream_input):
            async for speech_segment_bytes, is_utterance_final_flag in vad_results_stream_input:
                if not speech_segment_bytes: # Should be filtered by VAD, but good practice
                    continue
                if is_utterance_final_flag:
                    logger.debug(f"[{client_id_str}] VAD indicated end of utterance. Setting finality event.")
                    vad_marked_utterance_as_final_event.set()
                yield speech_segment_bytes
        
        # Main audio processing pipeline task definition
        async def audio_processing_pipeline():
            current_utterance_id = uuid.uuid4()
            # Tracks the start time of the current transcript segment relative to the current utterance.
            current_utterance_segment_start_time_s = 0.0 

            # Setting up the stream processing chain
            vad_input_audio_stream = audio_bytes_from_websocket_producer()
            vad_processed_stream = vad_processor.process_audio_stream(vad_input_audio_stream)
            whisper_input_speech_stream = vad_speech_adapter_for_whisper(vad_processed_stream)
            
            async for whisper_transcription_result in whisper_processor.transcribe_stream(whisper_input_speech_stream):
                if not whisper_transcription_result or not whisper_transcription_result.get("text", "").strip():
                    logger.debug(f"[{client_id_str}] Whisper returned no usable text. Skipping.")
                    continue

                is_this_transcription_final = vad_marked_utterance_as_final_event.is_set()
                
                # Prepare data for WebSocket message. Timestamps are utterance-relative.
                ws_msg_data = {
                    "text": whisper_transcription_result["text"],
                    "ts_start": round(current_utterance_segment_start_time_s, 3),
                    "ts_end": round(current_utterance_segment_start_time_s + whisper_transcription_result["duration"], 3),
                    "utterance_id": current_utterance_id,
                    "speaker": session_id, # Use session_id as a placeholder for speaker
                }

                if is_this_transcription_final:
                    logger.info(
                        f"[{client_id_str}] Processing FINAL transcript for utterance {current_utterance_id}: \"{ws_msg_data['text'][:50]}...\""
                    )
                    confidence_score = None # Default to None
                    if whisper_transcription_result.get("segments"):
                        try:
                            first_segment_api = whisper_transcription_result["segments"][0]
                            if "avg_logprob" in first_segment_api and first_segment_api["avg_logprob"] is not None:
                                # avg_logprob is typically negative. Closer to 0 is better.
                                # math.exp(avg_logprob) converts to a probability-like value (0 to 1).
                                confidence_score = round(math.exp(first_segment_api["avg_logprob"]), 4)
                        except (IndexError, TypeError, KeyError) as e_conf:
                            logger.warning(f"[{client_id_str}] Could not extract confidence: {e_conf}")


                    final_msg_to_client = WebSocketTranscriptFinal(**ws_msg_data, confidence=confidence_score)
                    await websocket.send_text(final_msg_to_client.model_dump_json())

                    final_msg_for_redis = TranscriptMessage(
                        utterance_id=current_utterance_id,
                        text=final_msg_to_client.text,
                        ts_start=final_msg_to_client.ts_start, # These are utterance-relative for now
                        ts_end=final_msg_to_client.ts_end,     # TODO: Consider absolute timestamps for Redis if global timeline needed
                        speaker=final_msg_to_client.speaker,
                        confidence=final_msg_to_client.confidence,
                    )
                    await redis_publisher.publish_transcript_message(final_msg_for_redis)
                    logger.info(f"[{client_id_str}] Published final transcript {current_utterance_id} to Redis.")

                    vad_marked_utterance_as_final_event.clear()
                    current_utterance_id = uuid.uuid4()
                    current_utterance_segment_start_time_s = 0.0
                else:
                    logger.debug(
                        f"[{client_id_str}] Processing PARTIAL transcript for utterance {current_utterance_id}: \"{ws_msg_data['text'][:50]}...\""
                    )
                    partial_msg_to_client = WebSocketTranscriptPartial(**ws_msg_data)
                    await websocket.send_text(partial_msg_to_client.model_dump_json())
                    current_utterance_segment_start_time_s += whisper_transcription_result["duration"]
                
                # Check for Whisper engine backpressure
                if whisper_processor.semaphore._value == 0: # type: ignore[attr-defined] # Accessing protected member for info
                    logger.warning(f"[{client_id_str}] Whisper engine at full capacity. Sending 'slow' signal to client.")
                    await websocket.send_text(WebSocketControlMessage(type="slow").model_dump_json())

        # Create and run the main processing pipeline task
        pipeline_task = asyncio.create_task(audio_processing_pipeline())
        await pipeline_task # This will run until client disconnects or an unhandled error in pipeline

    except WebSocketDisconnect:
        logger.info(f"[{client_id_str}] WebSocket disconnected by client for session {session_id}.")
    except Exception as e_main_handler:
        logger.error(f"[{client_id_str}] Unhandled error in WebSocket main handler for session {session_id}: {e_main_handler}", exc_info=True)
        try:
            if websocket.application_state == websocket.application_state.CONNECTED: # Starlette uses application_state
                 await websocket.send_text(
                    WebSocketControlMessage(type="error", message="An internal server error occurred.").model_dump_json()
                )
        except Exception as e_send_error: # Catch errors during sending the error message itself
            logger.error(f"[{client_id_str}] Failed to send error message to client: {e_send_error}")
    finally:
        logger.info(f"[{client_id_str}] Cleaning up WebSocket connection for session {session_id}.")
        manager.disconnect(websocket, client_id_str)
        if pipeline_task and not pipeline_task.done():
            logger.info(f"[{client_id_str}] Cancelling audio processing pipeline task for session {session_id}.")
            pipeline_task.cancel()
            try:
                await pipeline_task # Allow cancellation to propagate and complete
            except asyncio.CancelledError:
                logger.info(f"[{client_id_str}] Audio processing pipeline task successfully cancelled for session {session_id}.")
            except Exception as e_task_cleanup: # Catch any other errors during task cleanup
                 logger.error(f"[{client_id_str}] Error during pipeline task cleanup for session {session_id}: {e_task_cleanup}", exc_info=True)

        if redis_publisher and redis_publisher._is_connected: # type: ignore[attr-defined] # Accessing protected member
            await redis_publisher.close()
        logger.info(f"[{client_id_str}] WebSocket connection for session {session_id} fully closed and resources released.")

# Example of how to include this router in your main FastAPI application:
# In your main.py or app factory:
# from speech_to_text.service import websocket as stt_websocket_router
# app.include_router(stt_websocket_router.router, prefix="/speech", tags=["Speech-to-Text Service"])
