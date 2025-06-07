# Dockerfile for MockPilot Demographic Classifier Service

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
        curl build-essential python3-dev \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry \
    && apt-get remove -y curl build-essential python3-dev \
    && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy dependency definition files for the demographic classifier service
COPY pyproject.toml poetry.lock* ./
RUN poetry install --without dev --no-interaction --no-ansi --no-root
COPY src/ ./src
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

# Copy the application source code for the demographic classifier
# Assumes this Dockerfile is in backend/demographic_classifier/ and src/ is backend/demographic_classifier/src/
COPY src/ ./src

# Ensure the .env file will be loaded correctly if placed in /app (the WORKDIR)
# The application's config.py uses python-dotenv which looks for .env in the current working directory.

# Change ownership of the app directory to the non-root user
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Expose the port the app runs on (default 8005 for demographic classifier)
EXPOSE 8005

# Command to run the application
# Uvicorn will serve the FastAPI app defined in demographic_classifier.main (src/demographic_classifier/main.py)
CMD ["uvicorn", "demographic_classifier.main:app", "--host", "0.0.0.0", "--port", "8005"]
