import asyncio
import json
import logging
from typing import Optional

import redis.asyncio as aioredis

# Use a try-except block for robust import of settings and logger
try:
    from ..config import settings  # Relative import for package use
    from ..models.messages import TranscriptMessage, WebSocketControlMessage
except ImportError:
    # Fallback for direct execution or if the package structure context is different
    # This assumes 'config.py' and 'models/messages.py' are in a 'speech_to_text' directory,
    # and this script is run from a context where 'speech_to_text' is discoverable.
    from speech_to_text.config import settings
    from speech_to_text.models.messages import TranscriptMessage, WebSocketControlMessage

logger = logging.getLogger(settings.SERVICE_NAME + ".publisher")


class RedisPublisher:
    """
    Handles publishing messages to Redis channels.
    """

    def __init__(self, config: Optional[type(settings)] = None):
        self.config = config if config else settings
        self.redis_client: Optional[aioredis.Redis] = None
        self.transcripts_channel_name: str = self.config.REDIS_TRANSCRIPTS_CHANNEL_NAME
        self.control_channel_name: str = (
            self.config.REDIS_WEBSOCKET_BACKPRESSURE_CHANNEL_NAME
        )
        self._is_connected = False
        logger.info(
            f"RedisPublisher initialized. Transcripts channel: '{self.transcripts_channel_name}', "
            f"Control channel: '{self.control_channel_name}'"
        )

    async def connect(self) -> bool:
        """
        Establishes a connection to the Redis server.
        Returns True if connection is successful, False otherwise.
        """
        if self._is_connected and self.redis_client:
            logger.debug("Already connected to Redis.")
            return True
        try:
            logger.info(f"Connecting to Redis at {self.config.REDIS_URL}...")
            self.redis_client = aioredis.from_url(
                str(self.config.REDIS_URL), decode_responses=False
            )  # Publish bytes/strings
            await self.redis_client.ping()
            self._is_connected = True
            logger.info("Successfully connected to Redis.")
            return True
        except (aioredis.exceptions.ConnectionError, aioredis.exceptions.TimeoutError) as e:
            logger.error(f"Failed to connect to Redis: {e}", exc_info=False) # Keep log cleaner for common issues
            self.redis_client = None
            self._is_connected = False
            return False
        except Exception as e:
            logger.error(
                f"An unexpected error occurred during Redis connection: {e}",
                exc_info=True,
            )
            self.redis_client = None
            self._is_connected = False
            return False

    async def close(self):
        """
        Closes the Redis connection.
        """
        if self.redis_client:
            try:
                await self.redis_client.close()
                logger.info("Redis connection closed.")
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}", exc_info=True)
            finally:
                self.redis_client = None
                self._is_connected = False

    async def publish_transcript_message(self, message: TranscriptMessage) -> bool:
        """
        Publishes a TranscriptMessage to the configured transcripts Redis channel.

        Args:
            message: The TranscriptMessage object to publish.

        Returns:
            True if publishing was successful, False otherwise.
        """
        if not self._is_connected or not self.redis_client:
            logger.warning(
                "Not connected to Redis. Attempting to connect before publishing transcript."
            )
            if not await self.connect():
                logger.error(
                    "Failed to connect to Redis. Cannot publish transcript message."
                )
                return False

        if not self.redis_client:  # Should be caught by above, but as a safeguard
            logger.error("Redis client is not available. Cannot publish transcript message.")
            return False

        try:
            # Serialize the Pydantic model to a JSON string
            message_json = message.model_dump_json()
            await self.redis_client.publish(self.transcripts_channel_name, message_json)
            logger.debug(
                f"Published TranscriptMessage (ID: {message.utterance_id}) to channel '{self.transcripts_channel_name}'"
            )
            return True
        except Exception as e:
            logger.error(
                f"Error publishing TranscriptMessage to Redis channel '{self.transcripts_channel_name}': {e}",
                exc_info=True,
            )
            return False

    async def publish_control_message(self, message: WebSocketControlMessage) -> bool:
        """
        Publishes a WebSocketControlMessage to the configured control Redis channel.

        Args:
            message: The WebSocketControlMessage object to publish.

        Returns:
            True if publishing was successful, False otherwise.
        """
        if not self._is_connected or not self.redis_client:
            logger.warning(
                "Not connected to Redis. Attempting to connect before publishing control message."
            )
            if not await self.connect():
                logger.error(
                    "Failed to connect to Redis. Cannot publish control message."
                )
                return False

        if not self.redis_client:  # Safeguard
            logger.error("Redis client is not available. Cannot publish control message.")
            return False

        try:
            message_json = message.model_dump_json()
            await self.redis_client.publish(self.control_channel_name, message_json)
            logger.debug(
                f"Published ControlMessage (Type: {message.type}) to channel '{self.control_channel_name}'"
            )
            return True
        except Exception as e:
            logger.error(
                f"Error publishing ControlMessage to Redis channel '{self.control_channel_name}': {e}",
                exc_info=True,
            )
            return False


# --- Example Usage (for testing this module directly) ---
async def _main_publisher_test():
    """Main function to test the RedisPublisher class."""
    # Ensure logger level is appropriate for testing
    if settings.LOG_LEVEL == "INFO":  # Temporarily elevate for test verbosity if needed
        logging.getLogger(settings.SERVICE_NAME).setLevel(logging.DEBUG)
        logger.setLevel(logging.DEBUG)
        logger.info("Temporarily set Publisher logger to DEBUG for test.")

    publisher = RedisPublisher(config=settings)

    if not await publisher.connect():
        logger.error("Could not connect to Redis for testing. Aborting publisher test.")
        return

    # Create a dummy TranscriptMessage
    from uuid import uuid4 # Import here to avoid circular dependency if models.py also runs __main__

    dummy_transcript_msg = TranscriptMessage(
        utterance_id=uuid4(),
        text="Hello from the publisher test!",
        ts_start=1.0,
        ts_end=3.5,
        speaker="TestSpeaker",
        confidence=0.99,
    )
    await publisher.publish_transcript_message(dummy_transcript_msg)

    # Create a dummy ControlMessage
    dummy_control_msg = WebSocketControlMessage(
        type="slow",
        message="System is experiencing high load.",
    )
    await publisher.publish_control_message(dummy_control_msg)

    # Test publishing without explicit connect (should auto-connect if disconnected)
    await publisher.close()  # Simulate disconnect
    logger.info("Simulated disconnect. Testing auto-reconnect on publish...")

    dummy_transcript_msg_2 = TranscriptMessage(
        utterance_id=uuid4(),
        text="Testing auto-reconnect publish!",
        ts_start=4.0,
        ts_end=6.0,
        speaker="TestSpeaker2",
        confidence=0.98,
    )
    await publisher.publish_transcript_message(dummy_transcript_msg_2)

    await publisher.close()
    logger.info("RedisPublisher test completed.")


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Basic logging setup for standalone script execution
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
        settings = settings.__class__() # Re-instantiate using the existing class
        # Reconfigure logging if settings changed log level
        logging.getLogger().setLevel(settings.LOG_LEVEL.upper())
        logger.setLevel(settings.LOG_LEVEL.upper())

    else:
        logger.warning(
            f".env file not found at {project_root_env}. Relying on environment variables."
        )
    
    # Info for user running the test
    redis_url_display = str(settings.REDIS_URL)
    if settings.REDIS_URL.password: # Obfuscate password for display
        redis_url_display = settings.REDIS_URL.copy(update={'password': '****'}).unicode_string()

    logger.info(f"Attempting to connect to Redis at {redis_url_display} for testing publisher.")
    logger.info("Ensure Redis is running and accessible for this test.")
    
    asyncio.run(_main_publisher_test())
