# Dockerfile for MockPilot Speech-to-Text Service

# Stage 1: Build stage (install dependencies)
FROM python:3.11-slim AS builder

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true

# Install Poetry
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential python3-dev python3-pip ffmpeg \
    && pip install "poetry==1.8.3" \
    && ln -s /usr/local/bin/poetry /usr/bin/poetry \
    && apt-get remove -y curl python3-pip \
    && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency definition files
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies only for caching
RUN poetry install --without dev --no-interaction --no-ansi --no-root

# Copy application source
COPY src/ ./src

# Install the project itself
RUN poetry install --without dev --no-interaction --no-ansi

# Stage 2: Final stage (runtime)
FROM python:3.11-slim AS final

# Set environment variables (same as builder for consistency, though POETRY_HOME might not be needed if venv is copied correctly)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Install runtime system dependencies.
# ffmpeg is required for local whisper audio processing.
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
# Torch and torchaudio are installed via pip by Poetry, their wheels usually bundle necessary libs.

# Create a non-root user and group
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv .venv

# Copy the application source code
# The context for this Dockerfile is backend/speech_to_text/
# So, src/ maps to backend/speech_to_text/src/
COPY src/ ./src
# If there are other assets at the root of backend/speech_to_text/ that are needed, copy them too.
# e.g. COPY README.md ./ (if needed by the app)

# Ensure the .env file will be loaded correctly if placed in /app
# The application's config.py uses python-dotenv which looks for .env in the current working directory.

# Change ownership to the non-root user
COPY --chown=appuser:appuser --chmod=755 run_service.sh ./
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8001
CMD ["bash", "run_service.sh"]
