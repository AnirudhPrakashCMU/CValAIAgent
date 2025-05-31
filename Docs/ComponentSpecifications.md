# Component Specifications – MockPilot  
*(Docs/ComponentSpecifications.md)*  

This document defines **detailed specifications** for every primary module in MockPilot.  
Each section uses the template:

1. Purpose & Scope  
2. Functional Requirements  
3. Non-Functional Requirements  
4. Interfaces & Data Contracts  
5. Implementation Notes  
6. Testing Strategy  
7. Security & Compliance  

---

## 1. Speech-to-Text Service (`speech_to_text`)  

### 1.1 Purpose & Scope  
Transcribe live meeting audio into sentence-level JSON messages with timestamps, publishing them to the system bus for downstream processing.

### 1.2 Functional Requirements  
- Accept duplex WebSocket stream of 16-kHz mono PCM or Opus frames.  
- Emit interim tokens ≤ 300 ms after speech detected; commit full sentence when VAD signals end.  
- Detect speaker changes when audio tracks are separate (future: diarization).  
- Provide confidence score per word.  
- Auto-reconnect if client drops for < 30 s.

### 1.3 Non-Functional  
| Metric | Target |
|--------|--------|
| Latency | ≤ 600 ms sentence commit |
| Throughput | 1 stream ⇢ 50 KB/s |
| Uptime | 99.5 % during meeting hours |

### 1.4 Interfaces  
#### WebSocket `/stream`  
Client → Server  
`binary` frames (`bytes`)  

Server → Client  
```json
{
  "type": "partial" | "final",
  "text": "string",
  "ts_start": 12.3,
  "ts_end": 13.8,
  "confidence": 0.87
}
```  

Redis publish (`chan:transcripts`) → `TranscriptMsg` model.

### 1.5 Implementation Notes  
- **Engine**: OpenAI Whisper large-v3 running on GPU; fallback to local whisper-cpp tiny for offline dev.  
- **VAD**: Silero; threshold 0.6, min-silence 350 ms.  
- Packet handling via `websockets` + asyncio queue; GPU batch size 4.

### 1.6 Testing  
- Unit: feed 5-s WAV fixture → assert ≥ 90 % WER vs ground truth.  
- Integration: Docker compose loopback audio, ensure pub/sub works.  
- Load: simulate 5 parallel streams with k6.

### 1.7 Security  
- No audio persisted beyond RAM ring-buffer.  
- TLS-only; JWT header `Authorization: Bearer <token>` validated.

---

## 2. Intent Extractor (`intent_extractor`)  

### 2.1 Purpose  
Identify “design intents” in transcript lines and extract structured metadata (component type, styles, brand references).

### 2.2 Functional Requirements  
- Consume messages from `chan:transcripts`.  
- For each final sentence, run detection pipeline:  
  1. Regex shortlist (`button|dropdown|modal|tab`).  
  2. If hit, quick JSON mapping; else call GPT-4 w/ prompt.  
- Output `IntentMsg` with confidence.

### 2.3 Non-Functional  
Latency ≤ 200 ms average; fallback path (GPT) ≤ 1 s.

### 2.4 Interfaces  
Redis in/out.  
`IntentMsg` schema:

```json
{
  "utterance_id": "uuid",
  "component": "button",
  "styles": ["hover", "pill"],
  "brand_refs": ["Stripe"],
  "confidence": 0.83,
  "speaker": "PM"
}
```

### 2.5 Implementation  
- Prompt stored in `prompt_templates/intent_extractor.txt`.  
- Caching layer (SHA1(sentence) → result) in Redis to avoid duplicate LLM hits.  

### 2.6 Tests  
- Golden tests: 50 labelled sentences.  
- Contract tests: JSON response validates against Pydantic schema.  

### 2.7 Security  
PII scrub: mask emails/urls before sending to LLM.

---

## 3. Trigger / Debounce Service (`trigger_service`)  

### 3.1 Purpose  
Decide when to instruct Code Generator to build a mock-up, avoiding duplicates.

### 3.2 Functional Requirements  
- Maintain sliding window (last 5 s).  
- Fire when:  
  • New `IntentMsg` with confidence ≥ 0.75 **AND**  
  • Silence gap ≥ 1.5 s **OR** cue words (“let’s build”).  
- Publish `DesignSpec`.

### 3.3 Interfaces  
Input: `chan:intents`  
Output: `chan:design_specs`  

`DesignSpec`:

```json
{
  "spec_id": "uuid",
  "component": "button",
  "theme_tokens": {"gradient": "purple-blue"},
  "interaction": "hover:scale-105",
  "source_utts": ["utt-1","utt-2"]
}
```

### 3.4 Implementation  
Pure Python async consumer; uses aio-redis streams for ordering.

### 3.5 Tests  
Simulated transcript feed verifying exactly one spec per idea.

---

## 4. Design Mapper (`design_mapper`)  

### 4.1 Purpose  
Translate brand/style cues into Tailwind tokens and design system primitives.

### 4.2 Requirements  
- Load `data/mappings.json` at startup (hot-reload on file change).  
- Provide `map(styles[], brand_refs[]) → theme_tokens{}`.  
- Guarantee deterministic output (no LLM).

### 4.3 Interfaces  
Python function call (library) + simple REST `/map` for debugging.

### 4.4 Implementation  
- JMESPath queries over JSON.  
- Caches last 100 calls (LRU).

---

## 5. Code Generator (`code_generator`)  

### 5.1 Purpose  
Generate valid, styled React component code from `DesignSpec`.

### 5.2 Functional Requirements  
- POST `/generate` returns JSON with `jsx`, `css_needed`, `named_exports`.  
- Use GPT-4 in `json_mode=true`; temperature 0.3.  
- Validate with `@babel/parser` (via `pynodejs`) that code compiles.  
- Reject if unsafe patterns (`document.cookie`, `<script>`).

### 5.3 Non-Functional  
Latency target: ≤ 1 s (P90).  
Cost budget: ≤ 150 tokens per request.

### 5.4 Error Handling  
- If GPT fails JSON schema: retry once with system message.  
- On persistent failure publish `component_error` event for UI.

### 5.5 Tests  
- Snapshot prompts; diff tolerance using `snapshottest`.  
- Syntax test: run parser for each output in suite.

### 5.6 Security  
- Strip inline event handlers except `onClick`.  
- Escape any user text via JSX `{sanitize(text)}` helper.

---

## 6. Sentiment Miner (`sentiment_miner`)  

### 6.1 Purpose  
Collect social posts matching design idea, perform semantic search, score sentiment.

### 6.2 Functional Requirements  
- Nightly scraper job populates Mongo cache (max 10 k posts/day).  
- On demand, query Weaviate `nearText(query, k=50)`.  
- Compute sentiment with `cardiffnlp/twitter-roberta-base-sentiment`.  
- Return histogram buckets: positive/neutral/negative.

### 6.3 Interfaces  
REST `/search?query=<text>&k=<int>`  
Response:

```json
{
  "query": "stripe hover button",
  "results": [
    { "text": "...", "sentiment": 0.92, "tags": ["Gen Z"] },
    ...
  ]
}
```

### 6.4 Implementation  
- Scrapy spiders with rotating proxies.  
- Embeddings via HF `sentence-transformers/all-MiniLM-L6-v2`; stored in Weaviate class `Post`.

### 6.5 Tests  
- Mock Weaviate; assert ≥ 80 % top-10 recall on labelled dataset.

### 6.6 Security  
- Respect API TOS; throttle to 1 req/s.  
- Remove usernames before storage.

---

## 7. Demographic Classifier (`demographic_classifier`)  

### 7.1 Purpose  
Tag social posts with demographic groups for insight slicing.

### 7.2 Requirements  
- Rule-based keywords + spaCy NER to detect self-described attributes.  
- Fallback GPT classification when confidence < 0.5.  
- Support tag set: `["Gen Z","Millennial","Designer","Frontend Dev","Backend Dev","PM"]`.

### 7.3 Interfaces  
gRPC `Classify(Post)` → `TagList`.

### 7.4 Implementation  
- spaCy pipeline fine-tuned on 2 k labelled posts.  
- Confidence formula: `0.6*model_prob + 0.4*rule_score`.

### 7.5 Tests  
Precision ≥ 0.7, Recall ≥ 0.6 on hold-out set.

---

## 8. Orchestrator API (`orchestrator`)  

### 8.1 Purpose  
Central stateful API & WebSocket hub for frontend.

### 8.2 Functional Requirements  
- REST for health, auth, misc.  
- WebSocket `/ws/:session_id` stream multiplexing:  
  `{"kind":"transcript"|"component"|"insight"|"error", ...}`  
- Manage per-session Redis keys (TTL 2 h).  

### 8.3 Interfaces  
See OpenAPI spec auto-generated from Pydantic models.

### 8.4 Implementation  
- **FastAPI** + **uvicorn** workers.  
- Uses `aioredis` pub/sub; fan-out to connected sockets.

### 8.5 Tests  
- Contract tests with `httpx`.  
- Chaos test: kill speech svc, ensure WS remains open and sends `service_down`.

---

## 9. Preview Renderer (`frontend/SandpackHost`)  

### 9.1 Purpose  
Live-render generated components safely in browser.

### 9.2 Requirements  
- Sandbox via Sandpack iframe with CSP `sandbox="allow-scripts"`.  
- Accept diff patches to avoid full reload.  
- Expose compile errors to parent UI.

### 9.3 Interfaces  
`window.postMessage({type:"code:update", files:{"/App.js": "..."}}, "*")`.

### 9.4 Implementation  
- CodeMirror 6 editor for manual tweaks.  
- Debounce 300 ms before Sandpack refresh.

### 9.5 Tests  
Playwright visual diff on generated preview.

---

## 10. Frontend Dashboard (`frontend`)  

### 10.1 Purpose  
Provide 3-panel UI: transcript stream, live mock-up preview, sentiment insights.

### 10.2 Functional Requirements  
- Connect to Orchestrator WS; virtualized transcript list.  
- Tailwind responsive layout; dark mode.  
- Insight graphs with Chart.js stacked bar & pie.  
- Export component as CodeSandbox share link.

### 10.3 Non-Functional  
Lighthouse performance ≥ 80, accessibility ≥ 90.

### 10.4 Interfaces  
Internal React props contracts documented via TypeScript types.

### 10.5 Tests  
- Jest unit for hooks.  
- Cypress E2E “happy path” script.

---

## 11. Cross-Cutting Concerns  

| Concern | Strategy |
|---------|----------|
| **Logging** | Structlog JSON; levels DEBUG→INFO via env |
| **Config** | `shared/config.py` env-driven pydantic settings |
| **Observability** | Prometheus `/metrics`; Grafana dashboards |
| **Error Handling** | Central `trace_id`; Sentry integration |
| **Secrets** | Google Secret Manager; `.env` only for local |

---

*End of Component Specifications*  
