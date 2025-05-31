# Component Implementation Guide – MockPilot  
*(Docs/ComponentImplementationGuide.md • v1.0 • 2025-05-31)*  

This guide drills from “what” to **precise “how”** for every MockPilot service, giving engineers a concrete recipe to stand‐up each micro-service, directory skeletons, algorithmic notes, and library choices.  
All examples assume **Python 3.11** (backend) and **Node 20** (frontend).

---

## 1. Speech-to-Text Service (`backend/speech_to_text/`)

### 1.1 Directory Skeleton
```
speech_to_text/
├── src/
│   ├── __init__.py
│   ├── config.py          # Pydantic settings
│   ├── models.py          # TranscriptMsg schema
│   ├── whisper_engine.py  # GPU / CPU abstraction
│   ├── vad.py             # Silero wrapper
│   ├── websocket.py       # FastAPI WebSocket endpoint
│   ├── publisher.py       # Redis pub helper
│   └── main.py            # FastAPI app factory
└── tests/
    ├── unit/
    └── integration/
```

### 1.2 Tech Stack
| Concern | Choice | Reason |
|---------|--------|--------|
| Transcription | OpenAI Whisper v3 via `openai.Audio` | Highest accuracy, streaming support |
| Fallback | `whisper-cpp` tiny model | CPU offline dev |
| VAD | `silero-vad` (PyTorch) | Fast, 1-line API |
| WebSocket | `fastapi` + `websockets` | Async, native Whisper bytes pipe |
| Messaging | `redis.asyncio` | Same bus for all svcs |

### 1.3 Core Flow
1. Client sends **16-kHz mono PCM** frames every ≤ 50 ms.  
2. `vad.py` buffers until speech, then yields chunks.  
3. `whisper_engine.py.transcribe_stream()` batches 4 chunks / GPU call.  
4. Send `partial` JSON every 400 ms; on VAD silence ≥ 350 ms send `final` and `publish_transcript(msg)`.

### 1.4 Algorithms & Parameters
```
SILERO_THRESHOLD = 0.6       # speech prob
MAX_QUEUE = 4                # GPU back-pressure
PARTIAL_INTERVAL = 0.4 s
```
Back-pressure: if internal queue > `MAX_QUEUE`, push `{ "type":"slow" }` WS frame.

### 1.5 Key Tests
- Unit: feed fixture WAV → assert WER ≤ 0.15 (`jiwer` lib).  
- Integration: spin WS -> receive JSON frames; verify Redis publish count.  
- Perf: `pytest-benchmark` ensure ≤ 600 ms sentence latency.

---

## 2. Intent Extractor (`backend/intent_extractor/`)

### 2.1 Structure
```
intent_extractor/
├── src/
│   ├── config.py
│   ├── models.py          # IntentMsg
│   ├── regex_rules.py
│   ├── gpt_client.py
│   ├── service.py         # consume transcripts → publish intents
│   └── main.py            # worker entrypoint
└── tests/
```

### 2.2 Pipeline
```
TranscriptMsg → RegexDetector → (hit?) → QuickMapping
                               ↘ miss
                        GPT-4 JSON mode prompt
                          ↘ validate via pydantic
                       IntentMsg → Redis:intents
```
Regex first (< 2 ms) reduces GPT cost by ~70 %.

Prompt stored in `prompt_templates/intent_v1.txt` with `json_schema` tool call.

### 2.3 Libs
- `openai.AsyncOpenAI`
- `regex` (faster than std `re`)
- `jsonschema` for extra safety

### 2.4 Important Edge-Cases
- Email/URL redaction before GPT call: `re.sub(r"\b[\w.-]+@[\w.-]+\.\w+\b","[email]",txt)`.  
- Retry once on invalid JSON; second failure → publish error event.

---

## 3. Trigger / Debounce Service (`backend/trigger_service/`)

### 3.1 Logic
```python
WINDOW = 5.0          # seconds
SILENCE_GAP = 1.5
CONF_THRESHOLD = 0.75
CUE_WORDS = {"let's build", "mock up"}
```
Maintain deque of last intents & transcript `ts_end`.  
Emit `DesignSpec` when:
```
new_intent.conf ≥ CONF_THRESHOLD  AND
( now - last_audio_ts ≥ SILENCE_GAP  OR  CUE_WORDS ∩ intent.text )
```
Deduplicate by `(component, styles, brand_refs)` SHA1 over sliding window.

### 3.2 Implementation Tips
- Use Redis Streams for ordered consumption (`XREADGROUP`).  
- Unit test with synthetic timelines (“talky users”).

---

## 4. Design Mapper (`backend/design_mapper/`)

### 4.1 Static Resources
`data/mappings.json`
```json
{
  "brands": {
    "stripe": { "gradient": "purple-blue", "ease": "ease-out" },
    "apple":  { "radius": "lg", "shadow": "md" }
  },
  "styles": {
    "hover":  { "interaction": "hover:scale-105" },
    "pill":   { "radius": "full" }
  }
}
```

### 4.2 Code Outline
```
design_mapper/
└── src/
    ├── loader.py      # reload on file change (watchdog)
    ├── mapper.py      # map_brands_styles() → theme_tokens
    └── api.py         # FastAPI /map route
```
Algorithm: merge brand + style dicts with **style wins** precedence.

### 4.3 Caching
LRU 100 entries via `functools.cache`.

---

## 5. Code Generator (`backend/code_generator/`)

### 5.1 Prompt Strategy
System msg: _“You are a senior front-end engineer. Return JSON only.”_  
User template:
```json
{
  "spec": {...},
  "required_schema": {
    "jsx": "string",
    "tailwind": "boolean",
    "named_exports": { "type":"array","items":{"type":"string"} }
  }
}
```
Temperature = 0.3; `response_format={"type":"json_object"}`.

### 5.2 Validation Pipeline
1. Parse JSON (`pydantic` `ComponentMsg`).  
2. Run `@babel/parser` (`subprocess.run(["node", "scripts/parse.js"])`).  
3. Strip disallowed patterns via AST walk (`ast` + `react-lint`).  
4. On fail → retry once with GPT “Fix JSON to satisfy schema”.  
5. Publish `components` channel.

### 5.3 File Layout
```
code_generator/
├── src/
│   ├── prompt_builder.py
│   ├── validator.py      # babel parse + security checks
│   ├── service.py        # REST /generate
│   └── main.py
└── scripts/parse.js      # Node AST validator
```

---

## 6. Sentiment Miner (`backend/sentiment_miner/`)

### 6.1 Data Flow
1. **Scraper job** (`scrapy`) pulls Reddit & Instagram posts nightly into MongoDB.
2. **Embedder** processes new posts → `all-MiniLM-L6-v2` vectors.
3. **Weaviate** stores `Post` class with vector + metadata.
4. `/search` endpoint:
   - Build query from `DesignSpec` keywords & brand refs.
   - `nearText` `k=50` search.
   - SaaS inference on `cardiffnlp/twitter-roberta-base-sentiment` for each post (batch).
5. Aggregate histogram + top N posts → `InsightMsg`.

### 6.2 Key Code
```
sentiment_miner/
├── src/
│   ├── ingest.py           # Scrapy → Mongo
│   ├── embed.py            # batch embed & upsert Weaviate
│   ├── sentiment.py        # RoBERTa scorer
│   ├── service.py          # FastAPI /search
│   └── main.py
└── spiders/
```

### 6.3 Performance
Cache embeddings in Weaviate; sentiment scoring batched 128 posts/GPU call.

---

## 7. Demographic Classifier (`backend/demographic_classifier/`)

### 7.1 Model
- spaCy pipeline fine-tuned on 2 k labelled social posts.  
- Rule engine (`regex`, keyword dictionaries) produces initial tag set + score.  
- If confidence < 0.5, call GPT few-shot JSON classification.

### 7.2 gRPC Server
`grpclib` async implementation:
```python
class DemoClassifier(DemoClassifierBase):
    async def Classify(self, stream):
        req = await stream.recv_message()
        tags, conf = classify(req.text)
        await stream.send_message(TagList(tags=tags))
```

---

## 8. Orchestrator (`backend/orchestrator/`)

### 8.1 Responsibilities
- WebSocket hub `/ws/{session}` (audio, events fan-out).  
- Manage Redis subscriptions per session (`asyncio.TaskGroup`).  
- REST session CRUD & health checks.  
- Rate-limit & auth.

### 8.2 File Map
```
orchestrator/
└── src/
    ├── config.py
    ├── deps.py            # JWT decode, Redis pool
    ├── ws.py              # WS handlers
    ├── routes.py          # REST
    ├── fanout.py          # pub/sub → WS
    └── main.py            # FastAPI factory
```

### 8.3 Scalability
Stateless; scale horizontally. Sticky sessions via `session_id` in WS URL, but Redis pub/sub ensures any replica can fan-out.

---

## 9. Frontend Dashboard (`frontend/`)

### 9.1 Stack
| Area | Lib |
|------|-----|
| Framework | React 19 + Vite |
| Styling | TailwindCSS v3 |
| State | Zustand |
| WS | `reconnecting-websocket` |
| Live preview | Sandpack |
| Charts | Chart.js 4 |
| Tests | Vitest + React Testing Library, Cypress |

### 9.2 Folder Layout
```
frontend/src/
├── hooks/                  # useWebSocket, useSpeech
├── components/
│   ├── TranscriptList.tsx
│   ├── InsightPanel.tsx
│   ├── PreviewSandbox.tsx
│   └── Layout.tsx
├── contexts/SessionCtx.tsx
├── pages/App.tsx
└── utils/sanitize.ts       # DOMPurify wrapper
```

### 9.3 Preview Sandbox
`PreviewSandbox` wraps Sandpack iframe. Code injection:
```ts
postMessage({type:"code:update", files:{"/App.js": jsx}}, "*");
```
CSP: `sandbox="allow-scripts"`; no inline JS allowed beyond React component.

### 9.4 Audio Capture
`MediaRecorder` API → 16 kHz PCM chunk (transcode via WebAssembly) → WS send `ArrayBuffer`.

---

## 10. Shared Utilities (`backend/shared/`)

- `models.py` – Pydantic v2 base classes (`BaseModelConfig` frozen).  
- `redis.py` – Async pool factory, JSON helpers (`json.dumps(..., separators=(",",":"))`).  
- `logging.py` – `structlog` config: trace_id, service field.  
- `exceptions.py` – Standard error → RFC 7807 builder.

---

## 11. Local Development Recipes

| Task | Command |
|------|---------|
| Run single svc | `poetry run uvicorn backend/speech_to_text/src/main:app --reload` |
| All services | `make dev` (docker-compose hot reload) |
| Generate component manually | `curl -XPOST localhost:8001/generate -d @spec.json` |

---

## 12. Future Enhancements

1. Replace Redis with **NATS JetStream** for at-least-once delivery.  
2. Add **prompts/critique_agent.py** to review generated JSX with another LLM.  
3. Integrate **opus** codec to cut audio bandwidth 3×.  
4. Use **Next.js 14 + React Server Components** for richer frontend SSR.

---

### Change Log

| Date | Ver | Author | Notes |
|------|-----|--------|-------|
| 2025-05-31 | 1.0 | Anirudh | Initial implementation guide |
