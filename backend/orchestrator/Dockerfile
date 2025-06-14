# Dockerfile for MockPilot Orchestrator Service

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
        curl build-essential python3-dev python3-pip \
    && pip install "poetry==1.8.3" \
    && ln -s /usr/local/bin/poetry /usr/bin/poetry \
    && apt-get remove -y curl python3-pip \
    && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency definition files for the orchestrator service
COPY pyproject.toml poetry.lock* ./

# Install runtime dependencies first (without the project) for better caching
RUN poetry install --without dev --no-interaction --no-ansi --no-root

# Copy application source code
COPY src/ ./src

# Install the project itself
RUN poetry install --without dev --no-interaction --no-ansi

# Stage 2: Final stage (runtime)
FROM python:3.11-slim AS final

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    # Add the virtual environment's bin directory to PATH
    PATH="/app/.venv/bin:$PATH"

# Create a non-root user and group for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Set working directory
WORKDIR /app

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv .venv

# Copy the application source code for the orchestrator
# Assumes this Dockerfile is in backend/orchestrator/ and src/ is backend/orchestrator/src/
COPY src/ ./src
COPY --chown=appuser:appuser --chmod=755 run_service.sh ./
# Ensure the .env file will be loaded correctly if placed in /app (the WORKDIR)
# The application's config.py uses python-dotenv which looks for .env in the current working directory.

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port the app runs on (default 8000 for orchestrator as per main.py example)
EXPOSE 8000

# Command to run the application via helper script
CMD ["bash", "run_service.sh"]
