import asyncio
import json
import logging
from typing import AsyncGenerator, Callable, List, Optional, Any, Coroutine

import redis.asyncio as aioredis

from ..config import settings
# Placeholder for potential message schema imports
# from ..models.schemas import (
#     ClientAudioChunkMessage,
#     ClientEditComponentMessage,
#     ClientControlMessage,
# )

logger = logging.getLogger(settings.SERVICE_NAME + ".redis_client")


class RedisClient:
    """
    Manages Redis connections and pub/sub operations for the Orchestrator service.
    """

    def __init__(self, config: Optional[type(settings)] = None):
        self.config = config if config else settings
        self.redis_url: str = str(self.config.REDIS_URL)
        self._redis_connection: Optional[aioredis.Redis] = None
        self._pubsub_client: Optional[aioredis.client.PubSub] = None
        self._is_connected: bool = False
        self._subscriber_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event() # Event to signal subscriber to stop

        logger.info(
            f"RedisClient initialized for URL: {self.config.REDIS_URL.host}:{self.config.REDIS_URL.port}"
        )

    async def connect(self) -> bool:
        """
        Establishes a connection to the Redis server.
        Returns True if connection is successful, False otherwise.
        """
        if self._is_connected and self._redis_connection:
            try:
                await self._redis_connection.ping()
                logger.debug("Already connected to Redis and connection is live.")
                return True
            except (aioredis.exceptions.ConnectionError, aioredis.exceptions.TimeoutError):
                logger.warning("Previously connected to Redis, but ping failed. Reconnecting.")
                self._is_connected = False # Force reconnect
                if self._redis_connection:
                    await self._redis_connection.close() # Ensure old connection is closed
                self._redis_connection = None

        try:
            logger.info(f"Attempting to connect to Redis at {self.redis_url}...")
            self._redis_connection = aioredis.from_url(
                self.redis_url, decode_responses=False # Keep as bytes for pub/sub initially
            )
            await self._redis_connection.ping()
            self._is_connected = True
            logger.info("Successfully connected to Redis.")
            return True
        except (aioredis.exceptions.ConnectionError, aioredis.exceptions.TimeoutError) as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=False)
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during Redis connection: {e}",
                exc_info=True,
            )
        
        self._is_connected = False
        self._redis_connection = None
        return False

    async def close(self):
        """
        Closes the Redis connection and stops any active subscriber.
        """
        logger.info("Closing RedisClient resources...")
        if self._subscriber_task and not self._subscriber_task.done():
            logger.info("Stopping active Redis subscriber task...")
            self._stop_event.set() # Signal the subscriber loop to exit
            try:
                await asyncio.wait_for(self._subscriber_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for subscriber task to stop. Cancelling.")
                self._subscriber_task.cancel()
            except Exception as e:
                logger.error(f"Error stopping subscriber task: {e}", exc_info=True)
            self._subscriber_task = None
        
        if self._pubsub_client:
            try:
                # Unsubscribe from all channels
                # Note: aioredis pubsub client might not need explicit unsubscribe on close
                # await self._pubsub_client.unsubscribe() # If needed
                await self._pubsub_client.close()
                logger.info("Redis PubSub client closed.")
            except Exception as e:
                logger.error(f"Error closing Redis PubSub client: {e}", exc_info=True)
            finally:
                self._pubsub_client = None

        if self._redis_connection:
            try:
                await self._redis_connection.close()
                logger.info("Redis connection closed.")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}", exc_info=True)
            finally:
                self._redis_connection = None
        
        self._is_connected = False
        self._stop_event.clear() # Reset event for potential reuse
        logger.info("RedisClient resources closed.")

    async def publish_message(self, channel: str, message: Any) -> bool:
        """
        Publishes a message to a specific Redis channel.
        The message is expected to be a Pydantic model or a dict that can be JSON serialized.
        """
        if not await self.connect(): # Ensure connection
            logger.error(f"Cannot publish message to channel '{channel}': Not connected to Redis.")
            return False
        
        if not self._redis_connection: # Should be caught by connect(), but for type safety
            logger.error("Redis connection is None, cannot publish.")
            return False

        try:
            if hasattr(message, "model_dump_json"): # Pydantic model
                message_payload_str = message.model_dump_json()
            elif isinstance(message, dict) or isinstance(message, list):
                message_payload_str = json.dumps(message)
            elif isinstance(message, str):
                message_payload_str = message
            elif isinstance(message, bytes): # Allow publishing raw bytes
                 message_payload_str = message # type: ignore[assignment]
            else:
                logger.error(f"Unsupported message type for publishing: {type(message)}")
                return False

            await self._redis_connection.publish(channel, message_payload_str)
            logger.debug(f"Message published to Redis channel '{channel}'.")
            return True
        except Exception as e:
            logger.error(
                f"Error publishing message to Redis channel '{channel}': {e}",
                exc_info=True,
            )
            return False

    async def _subscriber_loop(
        self,
        channels: List[str],
        message_handler: Callable[[str, bytes], Coroutine[Any, Any, None]],
    ):
        """Internal loop for listening to Redis Pub/Sub messages."""
        while not self._stop_event.is_set():
            if not await self.connect():
                logger.warning("Subscriber loop: Redis connection failed. Retrying in 5 seconds...")
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    continue # Retry connection
                else:
                    break # Stop event was set

            if not self._redis_connection: # Should be caught by connect()
                logger.error("Subscriber loop: Redis connection is None. Cannot proceed.")
                await asyncio.sleep(5)
                continue

            try:
                if not self._pubsub_client or not self._pubsub_client.connection:
                    self._pubsub_client = self._redis_connection.pubsub()
                    await self._pubsub_client.subscribe(*channels)
                    logger.info(f"Subscribed to Redis channels: {channels}")

                # Listen for messages
                # The timeout helps to periodically check the _stop_event
                message = await self._pubsub_client.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message:
                    if message["type"] == "message":
                        channel_name = message["channel"].decode("utf-8") # Assuming channel names are utf-8
                        data_bytes = message["data"] # Data is bytes
                        logger.debug(f"Received message from Redis channel '{channel_name}'. Data length: {len(data_bytes)} bytes.")
                        try:
                            await message_handler(channel_name, data_bytes)
                        except Exception as e_handler:
                            logger.error(
                                f"Error in message_handler for channel '{channel_name}': {e_handler}",
                                exc_info=True,
                            )
                    elif message["type"] == "subscribe":
                         logger.info(f"Successfully subscribed to channel: {message['channel'].decode('utf-8')}")
                    # Handle other message types if necessary (e.g., psubscribe, unsubscribe)
                
                # Check connection health periodically if no messages are received
                if message is None:
                    await self._redis_connection.ping() # Keepalive/check connection

            except (aioredis.exceptions.ConnectionError, aioredis.exceptions.TimeoutError) as e_conn:
                logger.warning(f"Redis connection error in subscriber loop: {e_conn}. Attempting to reconnect...")
                if self._pubsub_client:
                    await self._pubsub_client.close() # Close pubsub before reconnecting redis_connection
                    self._pubsub_client = None
                if self._redis_connection:
                    await self._redis_connection.close()
                    self._redis_connection = None
                self._is_connected = False
                # Brief pause before attempting to reconnect in the next loop iteration
                await asyncio.sleep(1)
            except Exception as e_loop:
                logger.error(f"Unexpected error in Redis subscriber loop: {e_loop}", exc_info=True)
                # Potentially fatal error, pause before retrying to avoid rapid failure loops
                await asyncio.sleep(5)
        
        logger.info("Redis subscriber loop has been stopped.")


    def start_subscriber(
        self,
        channels: List[str],
        message_handler: Callable[[str, bytes], Coroutine[Any, Any, None]],
    ) -> asyncio.Task:
        """
        Starts a background task that subscribes to specified Redis channels
        and calls the message_handler for each received message.

        Args:
            channels: A list of channel names to subscribe to.
            message_handler: An async callable that takes (channel_name: str, message_data: bytes)
                             and processes the message.

        Returns:
            The asyncio.Task object for the running subscriber loop.
        """
        if not channels:
            logger.warning("No channels provided for Redis subscriber. Not starting.")
            # Return a completed dummy task or raise error
            async def dummy_task_func(): pass
            return asyncio.create_task(dummy_task_func())


        if self._subscriber_task and not self._subscriber_task.done():
            logger.warning("Redis subscriber task is already running. Stopping existing one before starting new.")
            # This path should ideally be avoided by managing the lifecycle externally.
            # For robustness, we can try to stop it.
            self._stop_event.set() # Signal old task to stop
            # Consider awaiting self.close() or similar logic if this is a common scenario.

        self._stop_event.clear() # Ensure stop event is clear for the new task
        logger.info(f"Starting Redis subscriber for channels: {channels}")
        self._subscriber_task = asyncio.create_task(
            self._subscriber_loop(channels, message_handler)
        )
        return self._subscriber_task

    async def stop_subscriber_task(self):
        """
        Signals the running subscriber task to stop and waits for it to complete.
        This is a more explicit way to stop than just calling `close()`.
        """
        if self._subscriber_task and not self._subscriber_task.done():
            logger.info("Signaling Redis subscriber task to stop...")
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._subscriber_task, timeout=10.0) # Wait with timeout
                logger.info("Redis subscriber task stopped successfully.")
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for subscriber task to stop gracefully. Cancelling.")
                self._subscriber_task.cancel()
                try:
                    await self._subscriber_task # Await cancellation
                except asyncio.CancelledError:
                    logger.info("Subscriber task was cancelled.")
            except Exception as e:
                logger.error(f"Error during subscriber task shutdown: {e}", exc_info=True)
            finally:
                self._subscriber_task = None
        else:
            logger.info("No active Redis subscriber task to stop.")
        
        # Clean up pubsub client if it exists
        if self._pubsub_client:
            try:
                await self._pubsub_client.close()
            except Exception: pass # Ignore errors on close during shutdown
            self._pubsub_client = None


# --- Example Usage (for testing this module directly) ---
async def _example_message_handler(channel_name: str, message_data: bytes):
    """Example message handler for testing the subscriber."""
    try:
        # Attempt to decode as JSON, but handle if it's not (e.g. raw string/bytes)
        message_str = message_data.decode('utf-8')
        logger.info(f"Example Handler: Received from '{channel_name}': '{message_str[:100]}...' (length: {len(message_data)})")
        # try:
        #     data_dict = json.loads(message_str)
        #     logger.info(f"  Parsed JSON: {data_dict}")
        # except json.JSONDecodeError:
        #     logger.info(f"  Data is not JSON: {message_str}")
    except UnicodeDecodeError:
        logger.info(f"Example Handler: Received binary data from '{channel_name}'. Length: {len(message_data)} bytes.")
    except Exception as e:
        logger.error(f"Error in example_message_handler: {e}", exc_info=True)


async def _main_redis_client_test():
    """Main function to test the RedisClient class."""
    if settings.LOG_LEVEL == "INFO":
        logging.getLogger(settings.SERVICE_NAME).setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.info("Temporarily set RedisClient logger to DEBUG for test.")

    redis_cli = RedisClient(config=settings)

    # Test connection
    if not await redis_cli.connect():
        logger.error("Failed to connect to Redis. Aborting test.")
        return

    # Test publisher
    test_channel = "orchestrator_test_channel"
    test_message_dict = {"type": "test", "content": "Hello from RedisClient test!", "timestamp": asyncio.get_event_loop().time()}
    
    logger.info(f"Publishing test message to '{test_channel}'...")
    await redis_cli.publish_message(test_channel, test_message_dict)

    # Test subscriber
    logger.info(f"Starting subscriber for channel '{test_channel}'...")
    subscriber_task = redis_cli.start_subscriber(
        channels=[test_channel, "another_test_channel"], # Subscribe to multiple
        message_handler=_example_message_handler,
    )

    # Let subscriber run for a bit and publish more messages
    await asyncio.sleep(1)
    await redis_cli.publish_message(test_channel, {"type": "test", "content": "Another message!"})
    await redis_cli.publish_message("another_test_channel", "Raw string message")
    
    await asyncio.sleep(3) # Let messages be processed

    # Test stopping subscriber
    logger.info("Stopping subscriber task...")
    await redis_cli.stop_subscriber_task() # Use the explicit stop method
    # The subscriber_task should be awaited/cancelled by stop_subscriber_task

    # Test closing the client (which also stops subscriber if still running)
    logger.info("Closing RedisClient...")
    await redis_cli.close()

    logger.info("RedisClient test completed.")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s",
        )
    logger.setLevel(logging.DEBUG)
    
    project_root_env = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..", ".env")
    )
    if os.path.exists(project_root_env):
        load_dotenv(dotenv_path=project_root_env)
        logger.info(f".env file loaded from {project_root_env}")
        settings = settings.__class__() # Re-instantiate
        logging.getLogger().setLevel(settings.LOG_LEVEL.upper())
        logger.setLevel(settings.LOG_LEVEL.upper())
    else:
        logger.warning(f".env file not found at {project_root_env}.")

    redis_url_display = str(settings.REDIS_URL)
    if settings.REDIS_URL.password:
        redis_url_display = settings.REDIS_URL.copy(update={'password': '****'}).unicode_string()
    logger.info(f"Attempting to connect to Redis at {redis_url_display} for testing RedisClient.")
    logger.info("Ensure Redis is running and accessible.")

    asyncio.run(_main_redis_client_test())
