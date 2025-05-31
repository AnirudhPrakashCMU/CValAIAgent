# Development Roadmap – MockPilot  
*(Docs/DevelopmentRoadmap.md)*  

This roadmap converts the overall project plan into a **time–boxed schedule** with concrete milestones, task breakdown, owners, and acceptance criteria.  
The primary context is a 36-hour hackathon sprint, followed by an optional one-week post-event hardening phase.

---

## 0. Legend  

| Abbrev. | Meaning                        |
|---------|--------------------------------|
| **STT** | Speech-to-Text Service         |
| **IE**  | Intent Extractor               |
| **TRG** | Trigger / Debounce Service     |
| **MAP** | Design Mapper                  |
| **CG**  | Code Generator                 |
| **ORCH**| Orchestrator API               |
| **FR**  | Frontend Dashboard + Preview   |
| **SM**  | Sentiment Miner                |
| **DC**  | Demographic Classifier         |

`⌛` = Estimated duration • `✔` = Deliverable

---

## 1. High-Level Milestones  

| # | Milestone | Duration | Key Deliverables |
|---|-----------|----------|------------------|
| 1 | Environment & CI Bootstrap | 3 h | Git repo, Docker Compose skeleton, GitHub Actions✔ |
| 2 | Real-time Transcription MVP | 5 h | STT WebSocket API, unit + integration tests✔ |
| 3 | Intent Extraction Pipeline | 4 h | IE service, prompt template, 50 golden tests✔ |
| 4 | Trigger Logic & ORCH Skeleton | 4 h | TRG service, FastAPI skeleton, Redis bus✔ |
| 5 | Code Generation Prototype | 4 h | CG REST `/generate`, syntax guard, snapshot tests✔ |
| 6 | Live Preview Frontend | 6 h | React UI (3-panel), Sandpack hot-reload, Cypress smoke✔ |
| 7 | Sentiment Mining & Vector DB | 6 h | Scraper stub, Weaviate index, search endpoint✔ |
| 8 | Demographic Tagging | 2 h | DC micro-service, rule engine, precision test✔ |
| 9 | End-to-End Demo & Load Test | 2 h | Docker-compose demo, k6 load script✔ |
|10 | Polish, Docs, Video Demo | 4 h | README, Architecture diagram, 60 s demo video✔ |

_Total Hackathon: **36 h**_

---

## 2. Detailed Hour-by-Hour Timeline  

| Hour | Task ID | Component(s) | Task Description | Owner | Dep. | Output |
|------|---------|-------------|------------------|-------|------|--------|
| 0-1  | 1.1 | All | Fork repo, create `MockPilot/` monorepo, init README | Anirudh | — | repo ✔ |
| 1-2  | 1.2 | All | Add pre-commit (black, isort, ESLint), Makefile | Dev-A | 1.1 | tooling ✔ |
| 2-3  | 1.3 | All | Docker Compose w/ Redis, stub svc containers | Dev-B | 1.1 | compose ✔ |
| 3-4  | 2.1 | STT | Whisper streaming wrapper + VAD | Dev-A | 1.x | `speech_service.py` ✔ |
| 4-5  | 2.2 | STT | WS server, pytest fixtures | Dev-A | 2.1 | tests ✔ |
| 5-6  | 2.3 | STT | Integration: audio→Redis transcripts | Dev-B | 2.2 | CI green ✔ |
| 6-8  | 3.1 | IE  | Regex detector, prompt template JSON mode | Dev-B | 2.3 | `intent_service.py` ✔ |
| 8-9  | 3.2 | IE  | 50 golden sentences, precision tests | Dev-B | 3.1 | tests ✔ |
| 9-10 | 4.1 | ORCH| FastAPI skeleton, health route | Anirudh | 1.x | `orchestrator/main.py` ✔ |
|10-11 | 4.2 | TRG | Debounce logic, sliding window | Dev-A | 3.x | `trigger_service.py` ✔ |
|11-12 | 4.3 | ORCH| Redis pub/sub fan-out, OpenAPI docs | Anirudh | 4.1 | docs ✔ |
|12-14 | 5.1 | MAP | Build `mappings.json`, mapper lib & tests | Dev-B | 3.x | mapping ✔ |
|14-16 | 5.2 | CG  | Prompt chain, syntax validation via Babel | Dev-A | 5.1 | `/generate` ✔ |
|16-18 | 6.1 | FR  | React setup, Tailwind config, transcript panel | Dev-B | 4.x | UI stub ✔ |
|18-19 | 6.2 | FR  | Sandpack iframe, WS consume transcripts | Dev-B | 6.1 | live text ✔ |
|19-22 | 6.3 | FR  | Component preview, insight side-panel | Anirudh | 5.x | live preview ✔ |
|22-24 | 7.1 | SM  | Reddit scraper stub, HF embeddings | Dev-A | 1.x | raw posts ✔ |
|24-26 | 7.2 | SM  | Weaviate docker, ingest, search endpoint | Dev-A | 7.1 | `/search` ✔ |
|26-27 | 8.1 | DC  | spaCy rules + model, REST classify | Dev-B | 7.2 | `/classify` ✔ |
|27-28 | 8.2 | SM  | Integrate DC tagging into search output | Dev-A | 8.1 | tagged results ✔ |
|28-30 | 9.1 | ALL | Compose all services, end-to-end smoke | Team | all prev | E2E demo ✔ |
|30-32 | 9.2 | ALL | k6 load test (5 sessions), optimize lat | Team | 9.1 | report ✔ |
|32-34 |10.1| ALL | Polish UI, 404 pages, error toasts | Dev-B | 9.1 | UX ✔ |
|34-36 |10.2| ALL | Record 60 s demo, finalize README, submit | Anirudh | all | submission ✔ |

---

## 3. Deliverables by Milestone  

| Milestone | Deliverables | Acceptance Criteria |
|-----------|--------------|---------------------|
| M1 | Repo & CI | `main` pipeline green, linters pass |
| M2 | STT MVP | WER ≤ 0.15 on sample, WS echo demo |
| M3 | IE Service | Precision ≥ 0.8 on golden set |
| M4 | Trigger & ORCH | `/ws` streams transcript + intents |
| M5 | CG Prototype | JSX parses with zero errors |
| M6 | Preview UI | Live component renders in browser within 2 s |
| M7 | Sentiment Search | Query returns ≥ 20 posts with sentiments |
| M8 | Demographic Tags | Classifier precision ≥ 0.7 |
| M9 | E2E Demo | Full flow operates on sample recording |
| M10| Submission | Video & docs uploaded, judges can run `docker-compose up` |

---

## 4. Post-Hackathon Hardening (Optional Week)  

| Day | Focus | Tasks | Outcome |
|-----|-------|-------|---------|
| 1 | Refactor | Modularize code, improve typing | Cleaner codebase |
| 2 | Observability | Add Prometheus & Grafana | Latency dashboards |
| 3 | Security | OWASP scan, CSP headers | Pen-test passed |
| 4 | Scalability | Horizontal autoscaling on Cloud Run | 15-session load pass |
| 5 | UX Polish | Figma plugin, dark mode tweaks | Designer approval |
| 6 | Docs | Developer guide, API reference site | docs.mockpilot.app |
| 7 | GA Launch | Production deploy, marketing site | v1.0 live |

---

## 5. Dependencies & Risk Buffers  

| Dependency | Risk | Buffer Allocated |
|------------|------|------------------|
| OpenAI API latency | Medium | +30 min in CG tasks |
| Social media API caps | High | Offline cache fallback in SM tasks |
| Whisper GPU access | Medium | Local whisper-cpp fallback (0.5× speed) |

_Total buffer inside schedule: **2 h** (already included)._  

---

## 6. Progress Tracking  

Progress is updated in **GitHub Projects board** and in `Docs/ProjectPlan.md` tables.  
Each merged PR **must** tick its checkbox in the roadmap by referencing task ID (e.g., `closes roadmap #5.2`).  

---

_End of Development Roadmap_  
