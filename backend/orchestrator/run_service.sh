#!/bin/bash
#
# Script to run the MockPilot Orchestrator service locally using Poetry.
#
# Prerequisites:
# 1. Poetry installed (https://python-poetry.org/docs/#installation)
# 2. Dependencies installed via `poetry install` in the `backend/orchestrator` directory.
# 3. An environment file (e.g., `.env`) in the `backend/orchestrator` directory or project root,
#    containing necessary environment variables like:
#    - REDIS_URL (e.g., redis://localhost:6379/0)
#    - JWT_SECRET_KEY (a strong, unique secret for JWT signing)
#    - LOG_LEVEL (optional, e.g., DEBUG for verbose logging)
#    - OPENAI_API_KEY (if Orchestrator directly uses OpenAI services)

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Navigate to the service's root directory (backend/orchestrator)
cd "$SCRIPT_DIR"

echo "🚀 Starting MockPilot Orchestrator Service..."

# Check if Poetry is installed
if ! command -v poetry &> /dev/null
then
    echo "❌ Poetry could not be found. Please install Poetry."
    echo "   Visit https://python-poetry.org/docs/#installation"
    exit 1
fi

# Check for .env file and remind user if not present (but don't fail)
# The application itself (via pydantic-settings) will look for .env in CWD or project root.
if [ ! -f ".env" ] && [ ! -f "../../.env" ]; then # Check in service dir and project root
    echo "⚠️  Warning: .env file not found in $(pwd) or project root (../../.env)."
    echo "   The service might not work correctly without required environment variables."
    echo "   Please ensure a .env file exists with at least:"
    echo "   REDIS_URL=redis://localhost:6379/0"
    echo "   JWT_SECRET_KEY=your_strong_jwt_secret_key_here"
    echo "   LOG_LEVEL=DEBUG" # Example for log level
    echo "   OPENAI_API_KEY=your_openai_api_key_here # If needed by orchestrator"
fi

# Define Uvicorn parameters
HOST="0.0.0.0"
PORT="8000" # Default port for the Orchestrator service
LOG_LEVEL_UVICORN_FROM_ENV=$(grep -E '^LOG_LEVEL=' .env 2>/dev/null | cut -d '=' -f2-)
if [ -z "$LOG_LEVEL_UVICORN_FROM_ENV" ] && [ -f "../../.env" ]; then
    LOG_LEVEL_UVICORN_FROM_ENV=$(grep -E '^LOG_LEVEL=' ../../.env 2>/dev/null | cut -d '=' -f2-)
fi
LOG_LEVEL_UVICORN="${LOG_LEVEL_UVICORN_FROM_ENV:-info}" # Use LOG_LEVEL from env if set, else default to info
RELOAD_FLAG="--reload" # Enable auto-reload for development

echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Uvicorn Log Level: $LOG_LEVEL_UVICORN"
echo "   Auto-reload: enabled"
echo ""
echo "🔗 Access the service API (e.g., health check) at http://$HOST:$PORT/v1/healthz"
echo "🔗 WebSocket endpoint (example): ws://$HOST:$PORT/v1/ws/test_session"
echo ""
echo "⏳ Waiting for Uvicorn to start... (Press Ctrl+C to stop)"
echo ""

# Run the Uvicorn server using Poetry
# The application path is `orchestrator.main:app` because Poetry handles the `src` layout.
poetry run uvicorn orchestrator.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level "$LOG_LEVEL_UVICORN" \
    $RELOAD_FLAG

echo "✅ MockPilot Orchestrator Service stopped."
