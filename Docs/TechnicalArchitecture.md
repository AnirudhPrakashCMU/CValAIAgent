# MockPilot – Technical Architecture  
*(Docs/TechnicalArchitecture.md)*  

## 1. Overview  

MockPilot is a distributed, event-driven system with Python micro-services on the backend and a React/Tailwind frontend. Services communicate through a mix of WebSocket streams and a Redis Pub/Sub message bus to guarantee sub-second propagation of design events from speech to live preview.

```
Zoom/Meet Audio
      │
 WebSocket (opus chunks)
      ▼
[Speech-to-Text]──transcript JSON──▶Redis(chan:transcripts)
      │                                             │
      │                    subscribe                │
      ▼                                             ▼
[Intention Extractor]──design-intent──▶Redis(chan:intents)
      │                                             │
      ▼                                             ▼
[Trigger Svc]──spec_ready──▶CodeGen REST──JSX out──▶Redis(chan:components)
      │                                             │
      ▼                                             ▼
[Sentiment Miner]────sentiments────▶Redis(chan:insights)
      │                                             │
      ▼                                             ▼
               <─── WebSocket ─── Frontend (React)
```

---

## 2. Services & APIs  

### 2.1 Speech-to-Text Service (`speech_to_text`)  
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/stream` | WebSocket | Accepts 16-kHz PCM or Opus frames (`bytes`) and returns interim/partial transcriptions (`{"text": "...", "ts_start": float, "ts_end": float}`) |

Implementation notes:  
- **Whisper V3** with `vad_options={"threshold":0.6}` to chunk speech.  
- Backpressure: server pings `{"type":"slow"}` if GPU queue > N=4.

### 2.2 Intent Extractor (`intent_extractor`)  
| Source | Sink |
|--------|------|
| Redis `transcripts` channel | Redis `intents` channel |

Algorithm: sliding window of last 3 sentences. If regex (`COMPONENT_RE`) hits or GPT confidence > 0.75, publish:

```json
{
  "utterance_id": "abc123",
  "component": "button",
  "styles": ["hover", "pill"],
  "brand_refs": ["Stripe"],
  "confidence": 0.83,
  "speaker": "PM"
}
```

### 2.3 Trigger & Debounce (`trigger_service`)  
Decides when to call CodeGen.  
Heuristic: require ≥1.5 s silence or explicit cue words ("let's build", "mock up"). Debounce window 5 s.

Publishes `design_spec`:

```json
{
  "spec_id": "spec-42",
  "component": "button",
  "theme_tokens": {"gradient":"purple-blue"},
  "interaction": "hover:scale-105"
}
```

### 2.4 Code Generator (`code_generator`)  
REST POST `/generate`  
Request: `DesignSpec` (above) → Response:

```json
{
  "spec_id": "spec-42",
  "jsx": "<button ...>Pay Now</button>",
  "tailwind": true,
  "named_exports": ["PayButton"]
}
```

LLM prompt enforced with `json_mode=true`. Post-generation, Node `@babel/parser` validates syntax.

### 2.5 Preview Renderer (frontend)  

The React app receives WebSocket pushes:

```ts
type ComponentEvt = {
  spec_id: string;
  jsx: string;
  ts: number;
};
```

Sandpack sandbox receives refreshed `files` map and hot-reloads.

### 2.6 Sentiment Miner (`sentiment_miner`)  
Cron + on-demand.  
- Scrapes Reddit & Instagram for queries like `"stripe button hover"` using official APIs.  
- Embeds via `sentence-transformers/all-MiniLM-L6-v2` then stored in **Weaviate**.  
- REST `/search?query=<text>&k=50` returns posts with `sentiment` (-1..1) and `embedding_distance`.

### 2.7 Demographic Classifier (`demographic_classifier`)  
FastAPI `/classify` POST. Accepts post body, returns:

```json
{
  "post_id": "...",
  "tags": ["Gen Z", "Frontend Dev"]
}
```

spaCy fine-tuned NER + rule-based keyword buckets, fallback GPT.

---

## 3. Data Models (Pydantic v2)  

```python
from pydantic import BaseModel, Field
from typing import List

class TranscriptMsg(BaseModel):
    text: str
    ts_start: float
    ts_end: float
    speaker: str | None = None

class IntentMsg(BaseModel):
    utterance_id: str
    component: str
    styles: List[str] = Field(default_factory=list)
    brand_refs: List[str] = Field(default_factory=list)
    confidence: float

class DesignSpec(BaseModel):
    spec_id: str
    component: str
    theme_tokens: dict
    interaction: str | None = None
```

Redis publishes/consumes these as `json().model_dump()` strings.

---

## 4. Communication Patterns  

| Pattern | Tech | Reason |
|---------|------|--------|
| Streaming audio & UI events | WebSocket | Low latency, duplex |
| Inter-service async events | Redis Pub/Sub | Lightweight, hackathon-friendly |
| LLM calls | HTTPS | OpenAI/Anthropic APIs |
| Bulk vector search | HTTP gRPC (Weaviate) | Nearest-neighbor |
| State persistence | Redis Hashes & TTL | Ephemeral meeting sessions |

Failure modes:  
- At-least-once delivery; services idempotent via `spec_id`/`utterance_id`.  
- Heartbeats: each service publishes `service:<name>:alive` every 10 s; orchestrator shows health.

---

## 5. Deployment Topology  

```
GCP Cloud Run
┌──────────────────────┐
│  backend-api (orch)  │ 80/443
└─────────┬────────────┘
          │ REST / WS
┌─────────▼────────────┐
│   Redis 7 (Memory)   │
└─────────┬────────────┘
          │ pub/sub
 ┌────────▼────────┐   ┌────────▼───────┐
 │ speech_service  │   │ intent_service │
 └─────────────────┘   └────────────────┘
      ... etc ...
Vercel (frontend) — pulls from `/api/ws` for live feed.
Weaviate cluster on GCP with attached MongoDB Atlas for raw post cache.
```

Docker Compose for local dev spins all containers plus **ngrok** tunnel for LLM callbacks.

---

## 6. Security & Compliance  

- Audio & transcripts stored **transiently** (TTL 7 days).  
- JWT auth between frontend and orchestrator.  
- CORS strict allowlist.  
- Generated JSX sanitized via `dompurify` before iframe injection.  
- Separate service account for social media scraping abiding by TOS.

---

## 7. Sequence Diagram – Happy Path  

```
Client        Orchestrator   STT Svc   Intent   Trigger   CodeGen   Frontend
 │ audio WS ▶ │             │         │         │         │
 │            │─pub:audio──▶│         │         │         │
 │            │            ┌┴┐        │         │         │
 │            │◀transcript─┤ │        │         │         │
 │            │─pub:xcript▶│ │        │         │         │
 │            │            └┬┘        │         │         │
 │            │◀intent──────┘         │         │         │
 │            │─pub:intent──────────▶┌┴┐        │         │
 │            │                      │ │        │         │
 │            │◀spec_ready───────────┤ │        │         │
 │            │──POST /generate─────▶│ │        │         │
 │            │                      └┬┘        │         │
 │            │◀component─────────────┘         │         │
 │◀ WS push ─ │                                             │
 │ live preview│                                             │
```

---

## 8. Observability  

- **Prometheus** sidecars for each Python service (expose `/metrics`).  
- Grafana dashboards: transcript latency, GPT latency, component generation success rate.  
- `elastic-apm` traces calls across services for E2E latency budgeting.

---

## 9. Extensibility Hooks  

| Hook | Location | Purpose |
|------|----------|---------|
| `post_generate(component)` | CodeGen | Lint or run AI critique |
| `on_insight(insight_json)` | Frontend | Custom visualization plugins |
| `design_mapper.yaml` | Data folder | Add new brand → token mappings |

---

## 10. Appendix – Env Vars  

| Variable | Default | Notes |
|----------|---------|-------|
| `OPENAI_API_KEY` | — | Whisper & GPT |
| `REDIS_URL` | `redis://redis:6379/0` | |
| `WEAVIATE_URL` | — | |
| `MONGODB_URI` | — | Sentiment cache |
| `JWT_SECRET` | dev-secret | rotate in prod |

