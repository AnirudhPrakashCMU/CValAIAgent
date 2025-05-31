#!/bin/bash
#
# Script to run the MockPilot Design Mapper service locally using Poetry.
#
# Prerequisites:
# 1. Poetry installed (https://python-poetry.org/docs/#installation)
# 2. Dependencies installed via `poetry install` in the `backend/design_mapper` directory.
# 3. An environment file (e.g., `.env`) in the `backend/design_mapper` directory or project root,
#    containing necessary environment variables like:
#    - MAPPINGS_FILE_PATH (optional, defaults to "data/mappings.json")
#    - LOG_LEVEL (optional, e.g., DEBUG for verbose logging)

# Exit immediately if a command exits with a non-zero status.
set -e

# Get the directory where the script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Navigate to the service's root directory (backend/design_mapper)
cd "$SCRIPT_DIR"

echo "🚀 Starting MockPilot Design Mapper Service..."

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
    echo "   The service will use default configuration values."
    echo "   You may want to create a .env file with settings like:"
    echo "   MAPPINGS_FILE_PATH=data/mappings.json"
    echo "   LOG_LEVEL=DEBUG"
    echo "   ENABLE_HOT_RELOAD=true"
fi

# Check if mappings.json exists in the default location
DEFAULT_MAPPINGS_PATH="../../data/mappings.json"
if [ ! -f "$DEFAULT_MAPPINGS_PATH" ]; then
    echo "⚠️  Warning: Default mappings file not found at $DEFAULT_MAPPINGS_PATH"
    echo "   Please ensure the mappings file exists or specify a custom path in .env"
    echo "   using MAPPINGS_FILE_PATH."
fi

# Define Uvicorn parameters
HOST="0.0.0.0"
PORT="8002" # Default port for the Design Mapper service
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
echo "🔗 API endpoint for mapping: http://$HOST:$PORT/v1/map"
echo "🔗 API documentation: http://$HOST:$PORT/v1/docs"
echo ""
echo "⏳ Waiting for Uvicorn to start... (Press Ctrl+C to stop)"
echo ""

# Run the Uvicorn server using Poetry
# The application path is `design_mapper.api:app` because Poetry handles the `src` layout.
poetry run uvicorn design_mapper.api:app \
    --host "$HOST" \
    --port "$PORT" \
    --log-level "$LOG_LEVEL_UVICORN" \
    $RELOAD_FLAG

echo "✅ MockPilot Design Mapper Service stopped."
