#!/bin/bash
#
# Script to run the MockPilot Speech-to-Text service locally using Poetry.
#
# Prerequisites:
# 1. Poetry installed (https://python-poetry.org/docs/#installation)
# 2. Dependencies installed via `poetry install` in the `backend/speech_to_text` directory.
# 3. An OpenAI API key set in a `.env` file in the `backend/speech_to_text` directory.
#    Example .env file content:
#    OPENAI_API_KEY=your_openai_api_key_here
#    LOG_LEVEL=DEBUG # Optional, for more verbose logging

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Navigate to the service's root directory (backend/speech_to_text)
cd "$SCRIPT_DIR"

echo "🚀 Starting MockPilot Speech-to-Text Service..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "❌ Poetry could not be found. Please install Poetry."
    echo "   Visit https://python-poetry.org/docs/#installation"
    exit 1
fi

# Check for .env file and remind user if not present (but don't fail)
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: .env file not found in $(pwd)."
    echo "   The service might not work correctly without an OPENAI_API_KEY."
    echo "   Please create a .env file with your OpenAI API key, e.g.:"
    echo "   OPENAI_API_KEY=your_openai_api_key_here"
    echo "   LOG_LEVEL=DEBUG" # Example for log level
fi

# Define Uvicorn parameters
HOST="0.0.0.0"
PORT="8001" # As configured in main.py example and Dockerfile
LOG_LEVEL_UVICORN="${LOG_LEVEL:-info}" # Use LOG_LEVEL from env if set, else default to info for uvicorn
RELOAD_FLAG="--reload" # Enable auto-reload for development

echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Uvicorn Log Level: $LOG_LEVEL_UVICORN"
echo "   Auto-reload: enabled"
echo ""
echo "🔗 Access the service (e.g., health check) at http://$HOST:$PORT/healthz"
echo "🔗 WebSocket endpoint (example): ws://$HOST:$PORT/v1/stream/test_session"
echo ""
echo "⏳ Waiting for Uvicorn to start... (Press Ctrl+C to stop)"
echo ""

# Run the Uvicorn server using Poetry
# The application path is `speech_to_text.main:app` because Poetry handles the `src` layout.
poetry run uvicorn speech_to_text.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level "$LOG_LEVEL_UVICORN" \
    $RELOAD_FLAG

echo "✅ MockPilot Speech-to-Text Service stopped."
