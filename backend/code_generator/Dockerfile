FROM python:3.11-slim AS builder
ENV POETRY_VERSION=1.8.3 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_IN_PROJECT=true

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && curl -sSL https://install.python-poetry.org | python3 - \
    && ln -s /opt/poetry/bin/poetry /usr/local/bin/poetry \
    && apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN poetry install --without dev --no-interaction --no-ansi --no-root
COPY src/ ./src
RUN poetry install --without dev --no-interaction --no-ansi

FROM python:3.11-slim AS final
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app
COPY --from=builder /app/.venv .venv
COPY src/ ./src
COPY README.md ./
USER nobody
EXPOSE 8003
CMD ["uvicorn", "code_generator.main:app", "--host", "0.0.0.0", "--port", "8003"]
