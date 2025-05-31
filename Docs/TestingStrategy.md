# Testing Strategy – MockPilot  
*(Docs/TestingStrategy.md – v1.1  2025-05-31)*  

This document defines **what, how, and when** we test every layer of the MockPilot platform, from a single function to a full multi-session load crawl.  
Version 1.1 extends v1.0 by adding concrete test cases, performance budgets, and acceptance criteria for each component.

---

## 1. Objectives  

1. Detect functional regressions within minutes of code change.  
2. Guarantee the core user journey *“speech → intent → mock-up → insight”* meets latency, accuracy, and stability SLAs.  
3. Provide quantitative quality bars that are enforced automatically in CI/CD.  
4. Keep the test suite fast (unit < 60 s, integration < 5 min) so developers run it on every commit.  
5. Enable repeatable, privacy-safe testing with deterministic fixtures.

---

## 2. Test Pyramid & Target Coverage  

| Layer | Tooling | Scope | Trigger | Coverage Goal |
|-------|---------|-------|---------|---------------|
| Unit (≈ 70 %) | `pytest`, `jest`, `vitest` | Single functions, React components | each commit | Py ≥ 90 %, TS ≥ 85 % |
| Integration (≈ 20 %) | `pytest-asyncio`, `httpx`, `toxiproxy` | Service boundaries (Redis, Weaviate, WS) | PR Gate | Critical paths |
| E2E / UI (≈ 8 %) | `Cypress`, `Playwright` | Full stack in browser via docker-compose | nightly & on tag | Happy path, error states |
| Load / Perf (≈ 2 %) | `k6`, `Locust`, `pumba` | Soak, stress, chaos | nightly & pre-release | P95 latency & resilience |

---

## 3. Component-Level Test Matrix  

### Legend  

• **U** = Unit test • **I** = Integration test • **P** = Performance / load test  

| Component | Test Case Description | Tool(s) | Type | Pass Criteria |
|-----------|-----------------------|---------|------|---------------|
| Speech-to-Text | 1. VAD splits on silence ≤ 350 ms<br>2. Transcript text WER against gold sample<br>3. WS back-pressure `"slow"` frame when GPU queue > 4 | `pytest`, `soundfile`, `websockets` | U, I | WER ≤ 0.15; latency ≤ 600 ms; back-pressure frame rate ≥ 90 % when saturated |
| Intent Extractor | 1. Regex hit on “dropdown” phrase<br>2. GPT JSON validity under token noise<br>3. Cache returns identical result on repeat input | `pytest`, `pytest-asyncio`, mocked OpenAI | U, I | Precision ≥ 0.8, recall ≥ 0.7; 100 % JSON schema validation |
| Trigger Service | 1. Sliding-window debounce emits ≤ 1 spec per intent<br>2. Fires on cue words “let’s build” despite no silence gap | `pytest` | U | False positive rate < 5 % |
| Design Mapper | 1. Brand “Stripe” + style “hover” → token `gradient:purple-blue`<br>2. Hot-reload keeps old output stable during update | `pytest`, `watchdog` | U | SHA-256 hash stable; reload completes < 200 ms |
| Code Generator | 1. JSX parses via Babel<br>2. Rejects injected `<script>` code<br>3. Retry logic returns valid JSON on first malformed run | `pytest`, Node `@babel/parser`, mocked GPT-4 | U, I | 0 syntax errors; unsafe pattern rejection = 100 % |
| Sentiment Miner | 1. Vector search returns ≥ 20 posts for “stripe button”<br>2. Sentiment classifier F1 on labelled dataset (100 posts) | `pytest`, `weaviate-client`, HF sentiment model | I | Sentiment accuracy ≥ 0.8; search recall ≥ 0.75 |
| Demographic Classifier | 1. Tag detection in “I’m a Gen Z dev”<br>2. gRPC streaming batch classify 50 posts | `pytest`, `grpcio-testing`, spaCy | U, I | Precision ≥ 0.7, recall ≥ 0.6 |
| Orchestrator | 1. WS fan-out to 3 clients (transcript, component, insight)<br>2. Message order preserved<br>3. Heartbeat drop triggers `service_down` | `pytest-asyncio`, `httpx`, `websockets` | I | 0 lost / reordered msgs in 10 000-msg run |
| Frontend Dashboard | 1. React hook renders new transcript in list<br>2. Sandpack refresh within 300 ms<br>3. Lighthouse accessibility score | `jest`, `vitest`, `Cypress`, `Lighthouse CI` | U, UI | Render time ≤ 300 ms; Lighthouse a11y ≥ 90 |

---

## 4. Integration Scenarios  

### 4.1 Happy Path  

1. Stream 2-min recorded meeting audio fixture.  
2. Expect ≥ 2 components and ≥ 1 insight panel.  
3. Measure total latency (first cue → component render) ≤ 2 s.  

### 4.2 Network Degradation  

– Inject 200 ms RTT + 2 % packet loss via `toxiproxy`.  
– Services must reconnect; UI shows “catching up” toast.  

### 4.3 Service Crash & Recovery  

– Kill `code_generator` container mid-session.  
– Orchestrator emits `service_down`, UI swaps to placeholder.  
– Restart container; next design idea must produce component within 3 s.  

### 4.4 Concurrent Sessions  

– Use `k6` to open 5 WS sessions with 1 chunk/50 ms audio.  
– Validate Redis channel fan-out integrity (`msg_loss=0`).  

---

## 5. End-to-End (E2E) Browser Tests  

| ID | Flow | Tool | Assertion |
|----|------|------|-----------|
| E2E-001 | User grants mic, speaks “pill button like Stripe” | Cypress | Component renders in Sandpack within 2 s |
| E2E-002 | User edits generated JSX; preview updates | Cypress | Δ renders ≤ 300 ms; no console errors |
| E2E-003 | Mobile viewport (375×812) | Playwright | Transcript panel collapses; buttons accessible |
| E2E-004 | Dark mode toggle | Playwright | Colours meet WCAG AA contrast |

---

## 6. Performance & Load Testing  

| Scenario | Tool | Metric | Threshold |
|----------|------|--------|-----------|
| 10 parallel sessions, 5 min | `k6` | Avg CPU / memory per svc | CPU < 70 %, Mem < 500 MB |
| Burst 200 DesignSpec/min | `k6`, `Locust` | CG P95 latency | ≤ 1 s |
| Redis Pub/Sub flood (100 k msgs) | custom Python | Msg loss, processing time | 0 loss; ≤ 2 s total |
| Browser perf | Lighthouse CI | TTI, CLS | TTI < 3 s, CLS < 0.1 |

Chaos experiments (`pumba`) randomly kill containers every 2 min; system must recover with zero data loss.

---

## 7. Test Data Management  

| Data | Source | Location | Notes |
|------|--------|----------|-------|
| Audio fixtures | Public-domain & synthetic TTS | `tests/fixtures/audio/` | ≤ 20 MB |
| Gold transcripts & intents | Manually annotated JSON | `fixtures/gold/` | Version-controlled |
| Social posts | Scraped & anonymised | `tests/fixtures/posts.json` | Usernames removed |
| Embeddings | Deterministic seed | regenerated if absent | Avoid committing large binary |

Large assets (> 50 MB) stored in GitHub LFS; CI restores via cache.

---

## 8. Tool Configuration Highlights  

```text
pytest.ini           --asyncio-mode=strict  --cov-report=xml
jest.config.mjs      testEnvironment: jsdom
cypress.config.ts    video: false, retries: 1
k6 scripts/          vus: 50, duration: 5m
toxiproxy.yaml       latency:200ms  loss:2%
```

---

## 9. Continuous Integration Gates  

| Stage | Fails If |
|-------|----------|
| Lint / Static | Any `black`, `isort`, `flake8`, `eslint` error |
| Unit Tests | Coverage below goals; failures |
| Integration | Contract mismatch; Redis / Weaviate docker up failures |
| Build | Docker image > 800 MB; build error |
| E2E | P90 latency > 2 s; UI violations |
| Load | P95 CG latency > 1 s |
| Security | `bandit`, `npm audit` critical findings |

CI publishes coverage to Codecov & perf dashboards to Grafana Cloud.

---

## 10. Local Developer Workflow  

```bash
# fast TDD loop
make test-unit      # < 60 s

# full pre-commit
make test           # unit + integration

# live-reload browser tests
npm run test:watch

# manual E2E fun mode
make e2e            # launches Cypress against docker-compose
```

---

## 11. Acceptance Criteria Summary  

| Milestone | Must Pass |
|-----------|-----------|
| M2 STT MVP | VAD & WER unit tests; integration WS echo demo |
| M3 Intent | Precision/recall on golden set; JSON schema validation |
| M4 Trigger + ORCH | Debounce contract tests; `/ws` fan-out |
| M5 CodeGen | Babel syntax OK; unsafe code rejection |
| M6 Preview UI | Cypress live render ≤ 2 s; Lighthouse perf > 80 |
| M7 Sentiment | Query recall ≥ 0.75; sentiment F1 ≥ 0.8 |
| M8 Demo Class. | Precision ≥ 0.7, recall ≥ 0.6 |
| M9 E2E Demo | Happy path latency ≤ 2 s; no message loss |
| Final GA | All CI gates green for 7 days consecutive |

---

## 12. Future Enhancements  

1. **Mutation testing** via `mutmut` / `stryker-js` to ensure test robustness.  
2. **Contract fuzzing** for WebSocket and Redis channels.  
3. **Shadow traffic replay** from production into staging to detect real-world edge cases.  
4. **Accessibility audits** automated with Axe CI.  

---

### Change Log  

| Date | Ver | Author | Notes |
|------|-----|--------|-------|
| 2025-05-31 | 1.0 | Anirudh | Initial strategy |
| 2025-05-31 | 1.1 | Anirudh | Added explicit test cases, perf budgets |
