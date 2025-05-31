# API Contracts – MockPilot  
*(Docs/APIContracts.md – v1.0 2025-05-31)*  

This document formalises **all public and inter-service interfaces** in MockPilot so that teams can develop, mock, and test services independently.  
It supersedes v0.1-alpha by adding full CRUD specs, error codes, authentication requirements, and message schemas.  

---

## 1. Conventions & Shared Specs  

| Item | Rule | Example |
|------|------|---------|
| Base URL | `https://api.mockpilot.app` (Cloud Run) | — |
| Path style | Kebab-case | `/generate-component` |
| Versioning | Semantic path prefix for breaking changes | `/v1/generate` |
| IDs | `uuid4` strings | `f0e24b9a-...` |
| Timestamps | RFC-3339 UTC | `2025-05-31T04:21:07Z` |
| Auth | JWT HS256 (`Authorization: Bearer <token>`) | — |
| Content-Type | `application/json; charset=utf-8` | — |
| Errors | RFC 7807 Problem Details | see §1.2 |
| Rate-limit | 429 w/ `x-rate-limit-*` headers | — |

### 1.1 Standard Headers  

| Header | Direction | Description |
|--------|-----------|-------------|
| `Authorization` | ⇢ | `Bearer <jwt>`; required except `/healthz` |
| `x-request-id` | ⇢/⇠ | Correlation UUID; echoed by server |
| `x-schema-version` | ⇢ | Client message schema (e.g. `1.0`) |
| `x-rate-limit-limit` | ⇠ | Max requests in current window |
| `x-rate-limit-remaining` | ⇠ | Remaining quota |
| `x-rate-limit-reset` | ⇠ | Epoch seconds until reset |

### 1.2 Problem Details Error Object  

```jsonc
{
  "type": "https://mockpilot.app/errors/validation",
  "title": "Invalid design spec",
  "status": 400,
  "detail": "theme_tokens.gradient is required",
  "instance": "/v1/generate",
  "trace_id": "ae1c0fe4-..."
}
```

Additional fields:  

| Field | Type | Notes |
|-------|------|-------|
| `trace_id` | string | Correlates logs across services |
| `errors` | object? | Field-level validation map |

---

## 2. Auth & Security  

1. JWT claims:  
   • `iss = "mockpilot"` • `aud = "mockpilot-users"` • `exp` future  
2. Services verify token using shared secret in Vault.  
3. Internal svc-to-svc auth: **mTLS** + allow-listed service accounts.  
4. WebSocket clients may pass token via query param `?token=` if headers unsupported.  
5. All traffic via HTTPS/TLS 1.3; HSTS 1 year.

---

## 3. Pub/Sub Message Bus (Redis)  

All messages are **stringified JSON** with mandatory `"schema_version":"1.0"`.

| Channel | Publisher | Subscribers | Payload Model |
|---------|-----------|-------------|---------------|
| `transcripts` | Speech-to-Text | Intent, Orchestrator | `TranscriptMsg` |
| `intents` | Intent Extractor | Trigger, Orchestrator | `IntentMsg` |
| `design_specs` | Trigger | CodeGen, Sentiment | `DesignSpec` |
| `components` | CodeGen | Orchestrator | `ComponentMsg` |
| `insights` | Sentiment Miner | Orchestrator | `InsightMsg` |
| `service:<name>:alive` | All | Prometheus exporter | `"pong"` |

### 3.1 Message Schemas  

```jsonc
// TranscriptMsg
{
  "schema_version": "1.0",
  "msg_id": "6201566a-9b99-4c09-9be8-2fb83e7ae4ad",
  "text": "Let's use a hover animation like Stripe.",
  "ts_start": 12.3,
  "ts_end": 15.1,
  "speaker": "PM",
  "confidence": 0.88
}

// IntentMsg
{
  "schema_version": "1.0",
  "utterance_id": "6201566a-...",
  "component": "button",
  "styles": ["hover"],
  "brand_refs": ["Stripe"],
  "confidence": 0.83,
  "speaker": "PM"
}

// DesignSpec
{
  "schema_version": "1.0",
  "spec_id": "9df34a57-...",
  "component": "button",
  "theme_tokens": { "gradient": "purple-blue" },
  "interaction": "hover:scale-105",
  "source_utts": ["6201566a-..."],
  "created_at": "2025-05-31T04:21:07Z"
}

// ComponentMsg
{
  "schema_version": "1.0",
  "spec_id": "9df34a57-...",
  "jsx": "<button class=\"...\">Pay Now</button>",
  "tailwind": true,
  "named_exports": ["PayButton"],
  "lint_passed": true,
  "generated_at": "2025-05-31T04:21:10Z"
}

// InsightMsg
{
  "schema_version": "1.0",
  "spec_id": "9df34a57-...",
  "sentiment_histogram": { "positive": 60, "neutral": 25, "negative": 15 },
  "demographic_breakdown": {
    "Gen Z": { "positive": 40, "neutral": 10, "negative": 5 },
    "Frontend Dev": { "positive": 20, "neutral": 8, "negative": 10 }
  },
  "top_posts": [
    { "post_id": "rdt_abc123", "text": "Stripe's hover is slick!", "sentiment": 0.92 }
  ],
  "generated_at": "2025-05-31T04:21:12Z"
}
```

---

## 4. Service APIs  

### 4.1 Speech-to-Text Service  

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/v1/stream` | WebSocket | JWT | Binary audio (`16-kHz PCM` or `Opus`) | JSON frames (`TranscriptPartial`, `TranscriptFinal`) |

Frame types:

```json
{ "type": "partial", "text": "Let's use a ho", "ts_end": 13.0 }
{ "type": "final", ... TranscriptMsg fields ... }
{ "type": "slow" }   // server back-pressure
```

Errors:  
`4401` WS close → invalid token • `4409` → rate-limit (`detail` field).

Rate-limit: 1 audio chunk / 50 ms.

---

### 4.2 Intent Extractor  

_No public HTTP endpoints._  

Debug:

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/v1/detect` | POST | `{ "text": "..." }` | `IntentMsg` |

429 after 30 req/min.

---

### 4.3 Design Mapper  

| Endpoint | Method | Body | Response |
|----------|--------|------|----------|
| `/v1/map` | POST | `{ "styles": ["hover"], "brand_refs": ["Stripe"] }` | `{ "theme_tokens": { "gradient": "purple-blue" } }` |

Validation errors → `400` Problem Details (`/errors/validation`).

---

### 4.4 Code Generator  

| Endpoint | Method | Auth | Body | Response |
|----------|--------|------|------|----------|
| `/v1/generate` | POST | JWT | `DesignSpec` | `ComponentMsg` |

Headers: `x-request-id` echoed.  
Rate-limit: 30 req/min per token.  

Errors:

| Status | Type | When |
|--------|------|------|
| 400 | `/errors/validation` | JSON schema invalid |
| 422 | `/errors/llm` | GPT returned malformed JSON twice |
| 429 | `/errors/rate-limit` | quota exceeded |
| 500 | `/errors/internal` | Unhandled |

---

### 4.5 Sentiment Miner  

| Endpoint | Method | Auth | Request | Response |
|----------|--------|------|---------|----------|
| `/v1/search` | GET | JWT | `query`, `k=50?` | `InsightMsg` (subset) |
| `/v1/posts/{post_id}` | GET | JWT | — | Raw post JSON |

Rate-limit: 20 req/min.  
`503 Service Unavailable` if scraper backlog > 90 % (Retry-After header in seconds).

---

### 4.6 Demographic Classifier (gRPC)  

```protobuf
service DemoClassifier {
  rpc Classify (Post) returns (TagList);
  rpc StreamClassify (stream Post) returns (stream TagList);
}
message Post { string id = 1; string text = 2; }
message TagList { repeated string tags = 1; }
```

Deadline: 1 s default. Error codes:  
`INVALID_ARGUMENT` (malformed text) • `RESOURCE_EXHAUSTED` (rate-limit) • `INTERNAL` (model failure).

---

### 4.7 Orchestrator API  

#### 4.7.1 WebSocket  

`GET /v1/ws/{session_id}?token=<jwt>`  

Client ⇢ Server:

| kind | Payload |
|------|---------|
| `audio` | `{ "kind":"audio", "data":"<base64 pcm>" }` |
| `edit_component` | `{ "kind":"edit_component", "spec_id":"...", "patch":"<diff>" }` |

Server ⇢ Client:

| kind | Model |
|------|-------|
| `transcript` | `TranscriptMsg` |
| `intent` | `IntentMsg` |
| `component` | `ComponentMsg` |
| `insight` | `InsightMsg` |
| `error` | Problem Details subset |
| `service_down` | `{ "service": "code_generator" }` |

Connection close codes:  
`4400` bad request • `4401` unauthenticated • `4403` forbidden (expired token) • `1013` server restart.

#### 4.7.2 REST  

| Endpoint | Method | Auth | Description | Response |
|----------|--------|------|-------------|----------|
| `/v1/healthz` | GET | — | Liveness probe | `{ "status":"ok" }` |
| `/v1/sessions` | POST | JWT | Create session | `{ "session_id": "uuid" }` |
| `/v1/sessions/{id}/summary` | GET | JWT | Meeting summary | `{ "highlights":[...], "components":[...], "insights":[...] }` |

---

## 5. Event-Driven Error Handling  

Each service publishing to Redis must also publish **error events** on channel `errors`. Schema:

```jsonc
{
  "schema_version": "1.0",
  "service": "code_generator",
  "level": "error",
  "trace_id": "ae1c0fe4-...",
  "timestamp": "2025-05-31T04:21:11Z",
  "error": {
    "type": "/errors/llm",
    "title": "LLM JSON decode failed",
    "detail": "Expecting property name at line 1 col 2"
  }
}
```

Orchestrator forwards a redacted version to frontend via WS `error` frame.

---

## 6. Rate Limits Summary  

| Service / Endpoint | Limit | Window | Headers Returned |
|--------------------|-------|--------|------------------|
| Speech WS | 1 chunk / 50 ms | — | — |
| CodeGen `/generate` | 30 req | 60 s | `x-rate-limit-*` |
| Sentiment `/search` | 20 req | 60 s | `x-rate-limit-*` |
| Orchestrator WS | 1 MB msg | frame | Close `1009` if exceeded |

---

## 7. Versioning & Compatibility  

1. **Minor/patch** additions are backward compatible.  
2. On any field removal/rename, increment path prefix (`/v2/...`) **and** bump `schema_version`.  
3. Frontend sends supported schema list in first WS frame:  
   `{ "client":"web","supported":["1.0","1.1"] }`  
   Server chooses highest mutual version.

---

## 8. Security Considerations  

| Threat | Mitigation |
|--------|------------|
| Token replay | JWT `exp` ≤ 30 min; refresh flow |
| Malicious JSX | Babel parse + DOMPurify + iframe sandbox |
| Over-posting | Pydantic model whitelist; unknown fields rejected |
| Data exfil via audio | Audio chunks not persisted; logs redacted |
| DDoS | Global CDN, WS connection limit (100 / IP) |

---

## 9. Appendix – Quick Reference Cheat-Sheet  

| Action | Method/Channel | Payload → Response |
|--------|----------------|--------------------|
| Stream audio | WS `/v1/stream` | bytes → `TranscriptPartial/Final` |
| Generate component | POST `/v1/generate` | `DesignSpec` → `ComponentMsg` |
| Query sentiment | GET `/v1/search?q=` | → `InsightMsg` |
| Frontend connect | WS `/v1/ws/{session}` | audio / edits ↔ events |
| Inter-svc bus | Redis `transcripts`, `intents`, … | see §3 |

---

*All changes to this contract require a PR, reviewer sign-off, and a bump to `schema_version`.*  
