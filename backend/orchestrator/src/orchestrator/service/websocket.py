from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any, Dict, List, Optional, Set

import websockets
from fastapi import APIRouter, Path, Query, WebSocket, WebSocketDisconnect, status
from starlette import status as http_status  # For WebSocket close codes

from ..config import settings
from ..models.schemas import (
    ClientAudioChunkMessage,
    ClientControlMessage,
    ClientEditComponentMessage,
    ComponentMsgPayload,
    DesignSpecPayload,
    InsightMsgPayload,
    IntentMsgPayload,
    OrchestratorWebSocketIncomingMessage,
    OrchestratorWebSocketOutgoingMessage,
    TranscriptMsgPayload,
    WSComponentMessage,
    WSErrorMessage,
    WSInsightMessage,
    WSIntentMessage,
    WSServiceStatusMessage,
    WSTranscriptMessage,
)
from ..utils import security

# RedisClient will be managed by the main application and the handler will be registered there.
# For now, this module will define the handler and the connection manager.

logger = logging.getLogger(settings.SERVICE_NAME + ".websocket")
router = APIRouter()


async def handle_client_edit_component(client: ClientConnection, data: Dict[str, Any]):
    msg = ClientEditComponentMessage(**data)
    logger.info(
        f"[{client.client_id}] Applying edit to spec {msg.spec_id} for session {client.session_id}"
    )
    await client.send_json_str(
        WSServiceStatusMessage(
            kind="service_status",
            service_name="orchestrator",
            status="up",
            message=f"edit_applied:{msg.spec_id}",
        ).model_dump_json()
    )


async def handle_client_control_session(client: ClientConnection, data: Dict[str, Any]):
    msg = ClientControlMessage(**data)
    logger.info(
        f"[{client.client_id}] Control action {msg.action} for session {client.session_id}"
    )
    await client.send_json_str(
        WSServiceStatusMessage(
            kind="service_status",
            service_name="orchestrator",
            status="up",
            message=f"action:{msg.action}",
        ).model_dump_json()
    )


class ClientConnection:
    """Represents an active WebSocket client connection."""

    def __init__(self, websocket: WebSocket, session_id: str):
        self.websocket = websocket
        self.session_id = session_id
        self.client_id = (
            f"{websocket.client.host}:{websocket.client.port}"
            if websocket.client
            else f"unknown-{uuid.uuid4()}"
        )
        self.outgoing_queue: asyncio.Queue[str] = asyncio.Queue(
            maxsize=settings.WEBSOCKET_MAX_QUEUE_SIZE
        )
        self.active: bool = True
        self.sender_task: Optional[asyncio.Task] = None
        self.receiver_task: Optional[asyncio.Task] = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.stt_ws: Optional[WebSocket] = None
        self.queue_full_count: int = 0

    async def send_json_str(self, json_str: str):
        """Puts a JSON string message onto the client's outgoing queue."""
        if not self.active:
            logger.warning(
                f"[{self.client_id}] Attempted to queue message for inactive connection. Session: {self.session_id}"
            )
            return
        try:
            self.outgoing_queue.put_nowait(json_str)
        except asyncio.QueueFull:
            logger.warning(
                f"[{self.client_id}] Outgoing queue full for session {self.session_id}. "
                f"Message dropped. Consider increasing WEBSOCKET_MAX_QUEUE_SIZE or handling backpressure."
            )
            self.queue_full_count += 1
            if self.queue_full_count > 3:
                logger.error(
                    f"[{self.client_id}] Disconnecting client due to persistent backpressure."
                )
                await self.close(code=http_status.WS_1011_INTERNAL_ERROR, reason="backpressure")

    async def close(
        self, code: int = status.WS_1000_NORMAL_CLOSURE, reason: Optional[str] = None
    ):
        """Gracefully closes the WebSocket connection and cancels associated tasks."""
        if not self.active:
            return
        self.active = False
        logger.info(
            f"[{self.client_id}] Closing connection for session {self.session_id}. Code: {code}, Reason: {reason}"
        )

        tasks_to_cancel = [self.sender_task, self.receiver_task, self.heartbeat_task]
        for task in tasks_to_cancel:
            if task and not task.done():
                task.cancel()

        # Allow tasks to process cancellation
        if any(tasks_to_cancel):
            await asyncio.gather(
                *[t for t in tasks_to_cancel if t], return_exceptions=True
            )

        if self.websocket.client_state != self.websocket.client_state.DISCONNECTED:
            try:
                await self.websocket.close(code=code, reason=reason)
            except RuntimeError as e:  # Can happen if already closed by client
                logger.debug(
                    f"[{self.client_id}] Error closing WebSocket (likely already closed): {e}"
                )
            except Exception as e:
                logger.error(
                    f"[{self.client_id}] Unexpected error closing WebSocket: {e}",
                    exc_info=True,
                )
        if self.stt_ws is not None:
            try:
                await self.stt_ws.close()
            except Exception:
                pass
        logger.info(
            f"[{self.client_id}] Connection resources cleaned up for session {self.session_id}."
        )


class ConnectionManager:
    """Manages active WebSocket client connections."""

    def __init__(self):
        self.active_connections: Set[ClientConnection] = set()
        self._lock = asyncio.Lock()  # To protect access to active_connections

    async def connect(self, client: ClientConnection):
        async with self._lock:
            self.active_connections.add(client)
        logger.info(
            f"Client {client.client_id} (Session: {client.session_id}) connected. Total active: {len(self.active_connections)}"
        )

    async def disconnect(self, client: ClientConnection):
        async with self._lock:
            if client in self.active_connections:
                self.active_connections.remove(client)
        await client.close()  # Ensure client resources are cleaned up
        logger.info(
            f"Client {client.client_id} (Session: {client.session_id}) disconnected. Total active: {len(self.active_connections)}"
        )

    async def broadcast(self, message_json_str: str):
        """Broadcasts a message to all active connections."""
        # Create a list of connections to iterate over to avoid issues if the set changes during iteration
        # (though send_json_str is non-blocking for the queue part)
        connections_to_send = list(self.active_connections)
        if not connections_to_send:
            logger.debug(f"Broadcast: No active connections to send message.")
            return

        logger.debug(
            f"Broadcasting message to {len(connections_to_send)} clients: {message_json_str[:100]}..."
        )
        for client in connections_to_send:
            if client.active:
                await client.send_json_str(message_json_str)


manager = ConnectionManager()


async def global_redis_message_handler(channel_name: str, data_bytes: bytes):
    """
    Handles messages received from subscribed Redis channels.
    Parses the message and broadcasts it to all connected WebSocket clients.
    This function is intended to be registered with the RedisClient subscriber.
    """
    logger.debug(
        f"Received message from Redis channel '{channel_name}'. Data length: {len(data_bytes)} bytes."
    )

    outgoing_message: Optional[OrchestratorWebSocketOutgoingMessage] = None
    message_str: Optional[str] = None

    try:
        message_str = data_bytes.decode("utf-8")
        payload_dict = json.loads(message_str)

        # Map Redis channel/payload to WebSocket message type
        if channel_name == settings.REDIS_SUBSCRIBE_CHANNELS[0]:  # "transcripts"
            parsed_payload = TranscriptMsgPayload(**payload_dict)
            outgoing_message = WSTranscriptMessage(**parsed_payload.model_dump())
        elif channel_name == settings.REDIS_SUBSCRIBE_CHANNELS[1]:  # "intents"
            parsed_payload = IntentMsgPayload(**payload_dict)
            outgoing_message = WSIntentMessage(**parsed_payload.model_dump())
        elif channel_name == settings.REDIS_SUBSCRIBE_CHANNELS[2]:  # "components"
            parsed_payload = ComponentMsgPayload(**payload_dict)
            outgoing_message = WSComponentMessage(**parsed_payload.model_dump())
        elif channel_name == settings.REDIS_SUBSCRIBE_CHANNELS[3]:  # "insights"
            parsed_payload = InsightMsgPayload(**payload_dict)
            outgoing_message = WSInsightMessage(**parsed_payload.model_dump())
        # Example for design_specs or service_status if needed:
        # elif channel_name == "design_specs":
        #     parsed_payload = DesignSpecPayload(**payload_dict)
        #     # outgoing_message = WSDesignSpecMessage(**parsed_payload.model_dump()) # If WSDesignSpecMessage exists
        #     logger.info(f"Received design_spec from Redis: {parsed_payload.spec_id}") # Log for now
        # elif channel_name == "service_status": # Assuming "service_status" is in REDIS_SUBSCRIBE_CHANNELS
        #     # The payload for service_status might be simpler, e.g. {"service_name": "stt", "status": "down"}
        #     outgoing_message = WSServiceStatusMessage(**payload_dict)
        else:
            logger.warning(
                f"Received message from unmapped Redis channel '{channel_name}': {message_str[:200]}"
            )
            return

    except json.JSONDecodeError:
        logger.error(
            f"Failed to decode JSON from Redis channel '{channel_name}': {message_str[:200] if message_str else 'Empty data'}",
            exc_info=True,
        )
        return
    except UnicodeDecodeError:
        logger.error(
            f"Failed to decode UTF-8 from Redis channel '{channel_name}'. Data (hex): {data_bytes.hex()[:100]}",
            exc_info=True,
        )
        return
    except Exception as e:  # Catch Pydantic validation errors or other issues
        logger.error(
            f"Error processing message from Redis channel '{channel_name}': {e}. Original data: {message_str[:200] if message_str else data_bytes.hex()[:100]}",
            exc_info=True,
        )
        return

    if outgoing_message:
        try:
            json_to_broadcast = outgoing_message.model_dump_json()
            await manager.broadcast(json_to_broadcast)
        except Exception as e:
            logger.error(
                f"Error serializing or broadcasting outgoing WebSocket message: {e}",
                exc_info=True,
            )


async def _websocket_sender_task(client: ClientConnection):
    """Sends messages from the client's outgoing queue to the WebSocket."""
    logger.info(
        f"[{client.client_id}] Sender task started for session {client.session_id}."
    )
    try:
        while client.active:
            try:
                message_json_str = await asyncio.wait_for(
                    client.outgoing_queue.get(), timeout=1.0
                )
                if (
                    client.active
                    and client.websocket.client_state
                    == client.websocket.client_state.CONNECTED
                ):
                    await client.websocket.send_text(message_json_str)
                    client.outgoing_queue.task_done()
                    logger.debug(
                        f"[{client.client_id}] Sent message to session {client.session_id}: {message_json_str[:100]}..."
                    )
                else:
                    logger.warning(
                        f"[{client.client_id}] WebSocket not connected or client inactive; cannot send. Message requeued or dropped if queue full."
                    )
                    # Potentially re-queue if important, or handle based on message type
                    # For now, if queue is full, it's dropped by send_json_str. If not full, it stays.
                    break  # Exit sender if client is not active or WS disconnected
            except asyncio.TimeoutError:
                # Timeout allows checking client.active periodically
                if not client.active:
                    break
                continue  # No message in queue, continue loop
            except (
                WebSocketDisconnect
            ):  # Should be caught by receiver, but good to handle here too
                logger.info(
                    f"[{client.client_id}] WebSocket disconnected during send. Session: {client.session_id}"
                )
                await manager.disconnect(client)
                break
            except Exception as e:
                logger.error(
                    f"[{client.client_id}] Error in sender task for session {client.session_id}: {e}",
                    exc_info=True,
                )
                # Depending on error, might need to disconnect client
                await manager.disconnect(client)  # Disconnect on unknown send error
                break
    except asyncio.CancelledError:
        logger.info(
            f"[{client.client_id}] Sender task cancelled for session {client.session_id}."
        )
    finally:
        logger.info(
            f"[{client.client_id}] Sender task stopped for session {client.session_id}."
        )


async def _websocket_receiver_task(client: ClientConnection):
    """Receives messages from the WebSocket client and processes them."""
    logger.info(
        f"[{client.client_id}] Receiver task started for session {client.session_id}."
    )
    try:
        while client.active:
            try:
                # Using a timeout for receive_text to allow periodic checks of client.active
                # and to prevent indefinite blocking if client goes silent without disconnecting.
                message_text = await asyncio.wait_for(
                    client.websocket.receive_text(),
                    timeout=settings.WEBSOCKET_HEARTBEAT_INTERVAL_S + 5.0,
                )
                logger.debug(
                    f"[{client.client_id}] Received message from client (Session {client.session_id}): {message_text[:100]}..."
                )

                # Attempt to parse as a known client message type
                try:
                    data_dict = json.loads(message_text)
                    kind = data_dict.get("kind")
                    parsed_message: Optional[OrchestratorWebSocketIncomingMessage] = (
                        None
                    )

                    if kind == "audio_chunk":
                        try:
                            parsed_message = ClientAudioChunkMessage(**data_dict)
                            if client.stt_ws is None:
                                client.stt_ws = await websockets.connect(
                                    str(settings.STT_SERVICE_WS_URL)
                                    + f"/{client.session_id}"
                                )
                            import base64

                            audio_bytes = base64.b64decode(parsed_message.data_b64)
                            await client.stt_ws.send(audio_bytes)
                        except Exception as e:
                            logger.error(
                                f"[{client.client_id}] Failed to forward audio to STT: {e}"
                            )
                    elif kind == "edit_component":
                        await handle_client_edit_component(client, data_dict)
                    elif kind == "control_session":
                        await handle_client_control_session(client, data_dict)
                    elif kind == "ping_custom":  # Example custom ping
                        await client.send_json_str(
                            WSServiceStatusMessage(
                                kind="service_status",
                                service_name="orchestrator",
                                status="up",
                                message="pong_custom",
                            ).model_dump_json()
                        )

                    else:
                        logger.warning(
                            f"[{client.client_id}] Received unknown message kind '{kind}' from client (Session {client.session_id})."
                        )

                    # if parsed_message:
                    #     logger.info(f"Parsed client message: {parsed_message}")

                except json.JSONDecodeError:
                    logger.warning(
                        f"[{client.client_id}] Received non-JSON message from client (Session {client.session_id}): {message_text[:200]}"
                    )
                except Exception as e_parse:  # Pydantic validation error etc.
                    logger.error(
                        f"[{client.client_id}] Error parsing client message (Session {client.session_id}): {e_parse}. Original: {message_text[:200]}",
                        exc_info=True,
                    )

            except asyncio.TimeoutError:
                # This means no message was received within the timeout.
                # It's an opportunity to check if the client is still active or send a ping.
                # FastAPI's WebSocket handles standard pings automatically if keepalive_timeout is set.
                # For now, just continue if client is active.
                if not client.active:
                    break
                logger.debug(
                    f"[{client.client_id}] Timeout waiting for client message. Session: {client.session_id}. Still active."
                )
                continue
            except WebSocketDisconnect:
                logger.info(
                    f"[{client.client_id}] WebSocket disconnected by client (receiver task). Session: {client.session_id}"
                )
                await manager.disconnect(client)
                break  # Exit loop
            except Exception as e:
                logger.error(
                    f"[{client.client_id}] Error in receiver task for session {client.session_id}: {e}",
                    exc_info=True,
                )
                await manager.disconnect(client)  # Disconnect on unknown error
                break
    except asyncio.CancelledError:
        logger.info(
            f"[{client.client_id}] Receiver task cancelled for session {client.session_id}."
        )
    finally:
        logger.info(
            f"[{client.client_id}] Receiver task stopped for session {client.session_id}."
        )


async def _websocket_heartbeat_task(client: ClientConnection):
    """Sends periodic pings to the client to keep the connection alive."""
    logger.info(
        f"[{client.client_id}] Heartbeat task started for session {client.session_id}."
    )
    try:
        while client.active:
            await asyncio.sleep(settings.WEBSOCKET_HEARTBEAT_INTERVAL_S)
            if (
                client.active
                and client.websocket.client_state
                == client.websocket.client_state.CONNECTED
            ):
                try:
                    # FastAPI's underlying Starlette WebSocket handles standard ping/pong.
                    # Sending a custom message can also serve as an application-level heartbeat.
                    # await client.websocket.send_text(WSServiceStatusMessage(kind="service_status", service_name="orchestrator", status="up", message="heartbeat").model_dump_json())
                    # For standard pings, we rely on FastAPI/Uvicorn's keepalive.
                    # If explicit pings are needed: await client.websocket.send_ping()
                    logger.debug(
                        f"[{client.client_id}] Heartbeat check for session {client.session_id}. (Relying on Uvicorn keepalive)"
                    )
                except WebSocketDisconnect:
                    logger.info(
                        f"[{client.client_id}] WebSocket disconnected during heartbeat. Session: {client.session_id}"
                    )
                    await manager.disconnect(client)
                    break
                except Exception as e:
                    logger.warning(
                        f"[{client.client_id}] Error sending heartbeat for session {client.session_id}: {e}"
                    )
            else:
                logger.info(
                    f"[{client.client_id}] Client no longer active or WebSocket disconnected; stopping heartbeat. Session: {client.session_id}"
                )
                break
    except asyncio.CancelledError:
        logger.info(
            f"[{client.client_id}] Heartbeat task cancelled for session {client.session_id}."
        )
    finally:
        logger.info(
            f"[{client.client_id}] Heartbeat task stopped for session {client.session_id}."
        )


@router.websocket("/v1/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str = Path(
        ..., description="Unique identifier for the client session."
    ),
    token: Optional[str] = Query(None, description="JWT token for authentication"),
):
    """
    WebSocket endpoint for MockPilot Orchestrator.
    - Establishes a connection for a given session_id.
    - Relays relevant messages from backend services (via Redis) to this client.
    - Handles messages sent from this client to the server.
    """
    if not token:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Missing authentication token"
        )
        return
    try:
        payload = security.decode_jwt_token(token)
        if payload.sub != session_id:
            await websocket.close(
                code=status.WS_1008_POLICY_VIOLATION, reason="Token subject mismatch"
            )
            return
    except Exception:
        await websocket.close(
            code=status.WS_1008_POLICY_VIOLATION, reason="Invalid or expired token"
        )
        return

    client = ClientConnection(websocket, session_id)
    await websocket.accept()
    await manager.connect(client)

    try:
        # Start sender, receiver, and heartbeat tasks for this client
        client.sender_task = asyncio.create_task(_websocket_sender_task(client))
        client.receiver_task = asyncio.create_task(_websocket_receiver_task(client))
        client.heartbeat_task = asyncio.create_task(_websocket_heartbeat_task(client))

        # Keep the endpoint alive while tasks are running.
        # Wait for either task to complete (e.g., due to disconnect or error).
        # We primarily rely on the receiver_task to detect client disconnects.
        if client.receiver_task:  # Should always be true
            await client.receiver_task  # This will block until receiver_task finishes

    except WebSocketDisconnect:  # This might be caught if receiver_task re-raises it
        logger.info(
            f"[{client.client_id}] WebSocket disconnected (caught in endpoint). Session: {client.session_id}"
        )
    except Exception as e:
        logger.error(
            f"[{client.client_id}] Unexpected error in WebSocket endpoint for session {client.session_id}: {e}",
            exc_info=True,
        )
        await client.close(
            code=http_status.WS_1011_INTERNAL_ERROR, reason="Internal server error"
        )
    finally:
        logger.info(
            f"[{client.client_id}] Cleaning up endpoint for session {client.session_id}."
        )
        # Disconnect will also ensure tasks are cancelled and connection removed from manager
        await manager.disconnect(client)
        logger.info(
            f"[{client.client_id}] Endpoint cleanup complete for session {client.session_id}."
        )


# Note: The global_redis_message_handler needs to be started by the main application
# (e.g., in main.py's startup event) by creating a RedisClient instance and
# calling its start_subscriber method with this handler.
