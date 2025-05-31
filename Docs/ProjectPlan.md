# MockPilot – Project Plan  
*(Docs/ProjectPlan.md – v1.0 2025-05-31)*  

---

## 1. Vision & Goals  

MockPilot is a real-time meeting copilot that listens to product discussions, detects UI/UX ideas, and within **≤ 2 s**:  

1. Generates functional React + TailwindCSS mock-ups.  
2. Renders a live preview that the team can tweak in-browser.  
3. Surfaces social-media sentiment (Reddit, Instagram, X) about similar designs, sliced by demographic.  

Success is measured by:  

| KPI | Target | Rationale |
|-----|--------|-----------|
| End-to-end latency (speech → mockup) | ≤ 2 s P95 | “Feels instant” in meetings |
| JSX parse success rate | 100 % | Never crash the preview |
| Sentiment recall on labelled set | ≥ 0.8 | Insight credibility |
| UI Lighthouse perf | ≥ 80 | Smooth user experience |

---

## 2. System Architecture Overview  

```
Audio WS  →  Speech-to-Text  →  Redis:transcripts  →  Intent Extractor
                              ↘                                   ↓
                               Orchestrator WS  ←  Redis:components ← Code Generator
                                                 ↙
                           Redis:insights ← Sentiment Miner ← Demographic Classifier
                                   ↓
                              Frontend (React + Sandpack live preview)
```

Communication patterns:  

| Link | Tech | Reason |
|------|------|--------|
| Audio & UI events | WebSocket | Low-latency duplex |
| Inter-service | Redis Pub/Sub | Fast, hackathon-friendly |
| Vector search | Weaviate HTTP | Built-in semantic k-NN |
| Demographic tagging | gRPC | Streaming batch calls |

Security: JWT auth at ingress, mTLS internal, sandboxed Sandpack iframe for generated code.

---

## 3. Component Breakdown & Technical Notes  

| # | Component | Purpose | Key Tech | Critical Tests |
|---|-----------|---------|----------|----------------|
| 1 | Speech-to-Text (STT) | Transcribe 16 kHz audio to JSON | Whisper API, websockets | WER ≤ 0.15; latency ≤ 600 ms |
| 2 | Intent Extractor (IE) | Detect design intents | Regex + GPT-4 JSON mode | Precision ≥ 0.8 on gold set |
| 3 | Trigger / Debounce (TRG) | Decide when to fire CodeGen | Sliding-window heuristics | ≤ 1 spec per idea on sim stream |
| 4 | Design Mapper (MAP) | Map styles/brands → tokens | Static JSON, JMESPath | Output hash deterministic |
| 5 | Code Generator (CG) | Produce JSX + Tailwind | GPT-4, Babel syntax guard | JSX compiles; no unsafe patterns |
| 6 | Sentiment Miner (SM) | Search & score posts | Scrapy, HF embeddings, Weaviate | Sentiment accuracy ≥ 0.8 |
| 7 | Demographic Classifier (DC) | Tag posts by group | spaCy + rules + GPT fallback | Precision ≥ 0.7 |
| 8 | Orchestrator (ORCH) | WS hub & state store | FastAPI, aioredis | 0 message loss in soak test |
| 9 | Frontend Dashboard (FR) | 3-panel UI & preview | React 19, Tailwind, Sandpack | P95 render ≤ 300 ms |

---

## 4. Project Directory Structure  

```
MockPilot/
├── backend/
│   ├── orchestrator/
│   ├── speech_to_text/
│   ├── intent_extractor/
│   ├── trigger_service/
│   ├── design_mapper/
│   ├── code_generator/
│   ├── sentiment_miner/
│   ├── demographic_classifier/
│   └── shared/           # config, utils, schemas
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   └── hooks/
│   └── tests/
├── infra/
│   ├── docker/
│   ├── k8s/
│   └── terraform/
├── data/
│   ├── mappings.json
│   └── vector_index/
├── Docs/
│   ├── ProjectPlan.md  ← (this file)
│   ├── ArchitectureDiagram.md
│   └── TestingStrategy.md
└── README.md
```

---

## 5. Implementation Timeline (36-Hour Hackathon Sprint)  

| Hour | Deliverable | Major Tasks | Owner | Acceptance |
|------|-------------|-------------|-------|------------|
| 0-3  | Repo & CI | Init monorepo, Docker compose, pre-commit | All | Lint & tests pass |
| 3-8  | STT MVP | Whisper streaming WS, publish transcripts | Dev A | WER test green |
| 8-12 | Intent Extraction | Regex fallback, GPT prompt, 50 golden tests | Dev B | Precision ≥ 0.8 |
| 12-15| Trigger & ORCH skeleton | Debounce logic, FastAPI health | Anirudh | `/ws` echoes transcript |
| 15-18| CodeGen prototype | Prompt chain, Babel syntax guard | Dev A | JSX parses ✓ |
| 18-24| Live Frontend | React UI, Sandpack preview hook | Dev B | Live reload ≤ 300 ms |
| 24-28| Sentiment Miner | Scraper stub, Weaviate deploy, search API | Dev A | `GET /search` returns ≥20 posts |
| 28-30| Demographic Classifier | spaCy model + gRPC server | Dev B | Precision ≥ 0.7 |
| 30-33| Insight Integration | ORCH fan-out, UI charts | Anirudh | Charts show demo data |
| 33-36| Polish & Demo | k6 load test, docs, video | Team | P95 latency ≤ 2 s |

_2 h buffer baked in for risk._

---

## 6. Testing & Quality Strategy  

| Layer | Tools | Frequency | Targets |
|-------|-------|-----------|---------|
| Unit (70 %) | pytest, jest | every commit | Py ≥ 90 % / TS ≥ 85 % cov |
| Integration (20 %) | pytest-asyncio, httpx, toxiproxy | PR gate | Contract adherence |
| E2E / UI (8 %) | Cypress, Playwright | nightly & tag | Core “speech → mockup” flow |
| Load / Chaos (2 %) | k6, pumba | nightly | P95 latency, failover |

Key scenarios: degraded network, service crash, concurrent sessions.

---

## 7. Tooling & Dependencies  

- **Python 3.11**, **Node 20**  
- Whisper, GPT-4 (json_mode), HF `all-MiniLM-L6-v2`  
- FastAPI, Uvicorn, Pydantic v2  
- Redis 7, Weaviate, MongoDB Atlas  
- React 19, TailwindCSS v3, Sandpack, Chart.js  
- Docker, GitHub Actions, GCP Cloud Run, Vercel  

---

## 8. Risks & Mitigation  

| Risk | Impact | Mitigation |
|------|--------|-----------|
| GPT latency spikes | Miss SLA | Cache, switch to Claude, template fallback |
| Social API caps | Sentiment gaps | Nightly cache warm-up, static dataset fallback |
| Unsafe generated code | Browser crash | Babel parse + DOMPurify + iframe CSP |
| Whisper GPU unavail | Transcription lag | whisper-cpp CPU fallback |

---

## 9. Living Document  

This plan will be updated at the end of each milestone. Commits that alter scope or architecture **must** include:  

1. Added / edited sections below the “Change Log” header.  
2. Version bump in file header.  

### Change Log  

| Date | Version | Author | Summary |
|------|---------|--------|---------|
| 2025-05-31 | 1.0 | Anirudh | Initial comprehensive plan |

