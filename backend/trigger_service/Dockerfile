# Dockerfile for MockPilot Trigger Service
FROM python:3.11-slim AS builder
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=1.8.3 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true
RUN apt-get update && apt-get install -y --no-install-recommends \
        curl build-essential python3-dev python3-pip \
    && pip install "poetry==1.8.3" \
    && ln -s /usr/local/bin/poetry /usr/bin/poetry \
    && apt-get remove -y curl python3-pip \
    && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN poetry install --without dev --no-interaction --no-ansi --no-root
COPY src/ ./src
RUN poetry install --without dev --no-interaction --no-ansi

FROM python:3.11-slim AS final
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"
RUN groupadd -r appuser && useradd -r -g appuser appuser
WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY src/ ./src
COPY --chown=appuser:appuser --chmod=755 run_service.sh ./
RUN chown -R appuser:appuser /app
USER appuser
EXPOSE 8006
CMD ["bash", "run_service.sh"]
