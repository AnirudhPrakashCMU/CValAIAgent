# Action Plan – Kick-off Phase (First 12 h)
*(Docs/ActionPlan.md • v1.1 • 2025-05-31)*  

This document zooms in on the **first 12 hours** of development, translating the global roadmap into concrete, time-boxed tasks.  
Scope covers: repository bootstrap, baseline CI/CD, **Speech-to-Text** MVP, **Orchestrator** skeleton, and **Frontend** stub.

---

## 0. Success Criteria (must be ✅ by +12 h)

| KPI | Target | Measured by |
|-----|--------|-------------|
| `make dev` spins up docker-compose without errors | ✅ | local run |
| `/backend/speech_to_text` WS echoes partial & final JSON for sample WAV | ✅ | `pytest tests/integration/test_stt_ws.py` |
| Orchestrator WS relays transcript frames to Frontend console | ✅ | Playwright e2e |
| Frontend (Vite) starts, connects WS, logs JSON frames | ✅ | `npm run dev` + browser |
| GitHub Actions CI (lint + unit) green on every push | ✅ | badge |

---

## 1. Hour-by-Hour Breakdown

| H | Task ID | Component | Description | Owner | Depends on | Deliverable |
|---|---------|-----------|-------------|-------|------------|-------------|
| 0-1 | 1.1 | Env | Fork / init monorepo, add LICENSE, baseline README | Anirudh | — | repo pushed |
| 1-2 | 1.2 | Env | Add `.gitignore`, **pre-commit** (black + isort + eslint), `Makefile`, Poetry & npm bootstrap | Dev A | 1.1 | `make lint` passes |
| 2-3 | 1.3 | Infra | Docker Compose skeleton: Redis + stub svc containers; GitHub Actions (`ci.yml`) running lint + tests | Dev B | 1.2 | CI green badge |
| 3-4 | 2.1 | STT | Directory skeleton (`speech_to_text/src/...`) with `config.py`, pydantic models | Dev A | 1.x | imports ok |
| 4-5 | 2.2 | STT | **Silero VAD** wrapper + unit test splitting demo audio | Dev A | 2.1 | `pytest -q` green |
| 5-6 | 2.3 | STT | Whisper stream mock (`whisper_engine.py.transcribe_stream`) returns dummy text; FastAPI WS `/v1/stream` endpoint | Dev A | 2.2 | WS client test passes |
| 6-7 | 2.4 | STT | On `final`, publish `TranscriptMessage` to Redis (`transcripts` chan) | Dev A | 2.3, Redis up | Redis CLI shows msg |
| 4-7 | 3.1 | ORCH | FastAPI app factory with `/healthz`; WS `/v1/ws/{session}` that pipes audio → STT WS and subscribes `transcripts` | Anirudh | 1.3, 2.3 | integration test |
| 5-8 | 4.1 | FE | Vite + React project scaffold; Tailwind config; `useWebSocket` hook connecting to Orchestrator, console-logs JSON | Dev B | 1.2, 3.1 | browser log |
| 8-9 | 5.1 | Wiring | `make dev` runs all containers; Play sample WAV through WS test client → see transcript in FE console | Team | 2-4 | demo gif |
| 9-10 | 6.1 | Tests | Add pytest + jest suites to CI; coverage gates 80 % | Dev A | 5.1 | CI green |
| 10-11 | 7.1 | Docs | Update `Docs/ProjectPlan.md`, generate this action plan, publish architecture diagram | Anirudh | 6.1 | docs pushed |
| 11-12 | 7.2 | Buffer | Fix flaky WS reconnect; tidy Docker tags; tag `kickoff-mvp` release | Team | all | git tag |

> Parallelism: STT (Dev A) and Orchestrator (Anirudh) overlap 4-7 h; Frontend (Dev B) starts once WS endpoint stable.

---

## 2. Detailed Task Tables

### 1. Environment & Tooling

| Task | Command / File | Output |
|------|----------------|--------|
| Pre-commit install | `make bootstrap` | hooks active |
| CI scaffold | `.github/workflows/ci.yml` | lint + tests |
| Compose up Redis | `infra/docker/docker-compose.yml` | `docker ps` shows redis |

### 2. Speech-to-Text MVP

| Step | Acceptance |
|------|------------|
| VAD splits demo audio (`tests/fixtures/intro.wav`) | ≥1 segment |
| WS `/v1/stream` echoes `{"type":"partial"}` then `{"type":"final"}` | client asserts order |
| Redis publish on final | `redis-cli` `SUBSCRIBE transcripts` shows JSON |

### 3. Orchestrator Skeleton

| Step | Acceptance |
|------|------------|
| `/healthz` returns 200 JSON | curl ok |
| WS `/v1/ws/foo` subscribes `transcripts` | receives relayed frames |
| Dockerfile builds <150 MB | `docker images` |

### 4. Frontend Stub

| Step | Acceptance |
|------|------------|
| `npm run dev` launches Vite | http://localhost:5173 |
| Console logs transcript JSON | browser devtools |

---

## 3. Dependencies Matrix

| Upstream | Downstream |
|----------|------------|
| Redis container | STT, Orchestrator |
| STT WS | Orchestrator → Frontend |
| pydantic models (shared) | STT, Orchestrator, FE types |

---

## 4. Risk & Mitigation (Kick-off)

| Risk | Mitigation |
|------|------------|
| Whisper API quota not ready | use dummy text stub until key active |
| VAD model download slow | cache model in repo CI layer |
| Cross-origin WS blocked | set CORS `*` in dev |

---

## 5. Deliverables Checklist

- [x] Repo & CI bootstrapped
- [x] Docker Compose with Redis + stub svcs
- [x] STT service streaming WS + Redis publish
- [x] Orchestrator WS hub relaying transcripts
- [ ] React frontend connects & logs JSON  
- [ ] GIF demo of end-to-end text flow  
- [ ] Docs updated & tag `kickoff-mvp`  

---

### Change Log

| Date | Ver | Author | Notes |
|------|-----|--------|-------|
| 2025-05-31 | 1.0 | Anirudh | Initial kick-off action plan |
| 2025-05-31 | 1.1 | Anirudh | Refined task owners, dependencies, success KPIs |

