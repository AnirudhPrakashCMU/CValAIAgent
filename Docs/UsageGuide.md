# Usage Guide – MockPilot
*(Docs/UsageGuide.md – v1.0 2025-05-31)*

This guide walks you through the exact steps to get MockPilot running on your machine once you have the codebase checked out and your API keys ready.

---

## 1. Prerequisites

1. **Docker ≥ 24** and **docker compose** installed.
2. **Python 3.11** and **Poetry** if you intend to run backend services locally.
3. **Node 20** and **npm ≥ 9** for the frontend (only needed for non-Docker workflows).
4. An OpenAI API key and other secrets for your `.env` file.

## 2. Configure Environment Variables

1. From the project root, run:
   ```bash
   scripts/setup_env.sh
   ```
   This creates `.env` from `.env-example` if it doesn't exist.
2. Open the newly created `.env` in your editor and replace all placeholders (e.g. `OPENAI_API_KEY=...`, `JWT_SECRET_KEY=...`, `MONGODB_URI=...`). Save the file.
   The default `STT_SERVICE_WS_URL` of `ws://speech_to_text:8001/v1/stream`
   works when running the stack via Docker Compose. Change it only if your
   speech-to-text service uses a different host or port.

## 3. One‑Command Startup (Recommended)

1. Run the helper script which creates `.env` (if needed), installs dependencies and spins up the stack:
   ```bash
   python3 scripts/setup_and_run.py
   ```
2. Wait for Docker images to build and services to start. The frontend will be available at `http://localhost:5173`.
3. Open the URL in your browser, allow microphone access, then click **Start** to begin streaming audio. Speak your design ideas and watch transcripts and components appear live.

## 4. Manual Setup

If you prefer running pieces individually:

1. **Bootstrap dependencies**
   ```bash
   make bootstrap
   ```
2. **Launch all services with Docker Compose**
   ```bash
   make dev
   ```
   The Makefile explicitly passes your `.env` file to Docker Compose so
   credentials like `OPENAI_API_KEY` are available to all services.
   You can also invoke Compose directly using
   `docker compose --env-file .env -f infra/docker/docker-compose.yml up --build`.
3. Access the frontend at `http://localhost:5173`, allow microphone use and hit **Start** to begin.

## 5. Stopping the Stack

```bash
make down  # or docker compose -f infra/docker/docker-compose.yml down
```

## 6. Troubleshooting Tips

- Use `make logs` to tail output from all services if something doesn't start.
- Ensure ports `5173`, `8000`, `6379`, `8080` and MongoDB's port are free.
- Confirm your API keys are valid and not rate limited.
- If `make bootstrap` fails with a message like "git failed", ensure Git is installed and run the command from the project root.

Once the services are up and the frontend loads, speaking a UI idea will generate components in real time. Happy prototyping!
