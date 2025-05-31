# Design Mapper Service – MockPilot  
*Path `backend/design_mapper/`*  

Translates **brand references** (e.g. `stripe`, `apple`) and **style cues** (e.g. `hover_lift`, `pill_button`) into:  

* **Theme tokens** – abstract design-system primitives  
* **Tailwind CSS utility classes** – concrete classes for the frontend preview  

It is **100 % deterministic** (no LLMs) and hot-reloads `mappings.json` at runtime, making it the single source-of-truth for design semantics inside MockPilot.

---

## 1. Directory Layout  

```
backend/design_mapper/
├── Dockerfile                 # Container image
├── run_service.sh             # Local dev helper
├── pyproject.toml             # Poetry project
├── README.md                  # ← you are here
└── src/design_mapper/
    ├── api.py                 # FastAPI entry-point
    ├── config.py              # Env-driven settings
    ├── service/
    │   └── mapper.py          # Core mapping logic
    ├── utils/loader.py        # File watcher + hot reload
    └── models/schemas.py      # Pydantic models
data/
└── mappings.json              # Brands, styles & token map
```

---

## 2. Configuration  

All options are environment-variable driven (see `config.py`). Common ones:

| Variable | Default | Description |
|----------|---------|-------------|
| `MAPPINGS_FILE_PATH` | `data/mappings.json` | Absolute/relative path to mapping file |
| `ENABLE_HOT_RELOAD` | `true` | Watch file & reload on change |
| `FILE_WATCH_INTERVAL_SECONDS` | `2.0` | Polling interval for watchdog |
| `ENABLE_LRU_CACHE` | `true` | Cache identical requests |
| `LRU_CACHE_MAXSIZE` | `100` | Max cached entries |
| `LOG_LEVEL` | `INFO` | Logging level |
| `API_VERSION` | `v1` | URL prefix for routes |
| `API_PORT` | `8002` | Listening port |

Create a `.env` (or use project-root `.env`) to override:

```
LOG_LEVEL=DEBUG
MAPPINGS_FILE_PATH=/workspace/mappings.json
```

---

## 3. Running the Service  

### 3.1 Docker (recommended)

```
# From repo root
docker compose -f infra/docker/docker-compose.yml up design_mapper
# or standalone:
cd backend/design_mapper
docker build -t mockpilot-design-mapper .
docker run -p 8002:8002 -v $PWD/../../data/mappings.json:/app/data/mappings.json mockpilot-design-mapper
```

### 3.2 Local with Poetry

```
cd backend/design_mapper
poetry install
poetry run uvicorn design_mapper.api:app --reload --port 8002
```

Hot-reload of both Python code (`--reload`) **and** `mappings.json` will now work.

---

## 4. REST API Reference  

All routes are prefixed with `/<API_VERSION>` (`/v1` by default).

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/v1/map` | Map brands & styles → theme tokens + Tailwind classes |
| POST | `/v1/reload` | Force reload of mapping file & clear caches |
| GET  | `/v1/healthz` | Service health & mapping stats |

### 4.1 POST `/v1/map`

**Request**

```json
{
  "styles": ["hover_lift", "pill_button"],
  "brand_refs": ["stripe"],
  "component": "button"
}
```

**Response**

```json
{
  "theme_tokens": {
    "primary_color_scheme": "blue-purple-gradient",
    "border_radius": "full",
    "padding_x": "px-6",
    "padding_y": "py-2",
    "interaction": "transform transition-transform duration-150 hover:scale-105 hover:shadow-lg",
    "button_style": "rounded-md",
    "font_family": "sans-serif",
    "text_color_primary": "white",
    "animation_ease": "ease-out-sine",
    "border_subtle": "border-transparent"
  },
  "tailwind_classes": [
    "bg-gradient-to-r",
    "from-blue-500",
    "to-purple-600",
    "rounded-full",
    "px-6",
    "py-2",
    "transform",
    "transition-transform",
    "duration-150",
    "hover:scale-105",
    "hover:shadow-lg"
  ],
  "source_styles": ["hover_lift", "pill_button"],
  "source_brands": ["stripe"]
}
```

### 4.2 POST `/v1/reload`

Reloads file **and** clears LRU cache.

```
curl -X POST http://localhost:8002/v1/reload
→ { "status":"success","message":"Mappings reloaded successfully" }
```

### 4.3 GET `/v1/healthz`

```
curl http://localhost:8002/v1/healthz
{
  "status": "ok",
  "service": "design_mapper",
  "mappings_loaded": true,
  "brands_count": 5,
  "styles_count": 18,
  "token_map_count": 20
}
```

---

## 5. Extending the Mapping Table  

`data/mappings.json` schema:

```jsonc
{
  "brands":      { "<brand_id>": { /* token overrides */ } },
  "styles":      { "<style_id>": { /* token overrides */ } },
  "tailwind_token_map": { "<abstract_token>": "<tailwind_class>" }
}
```

Precedence when merging:

1. Style properties override brand properties.  
2. Later items in the request list override earlier ones.  
3. Missing keys fall back to `ThemeTokens` defaults.

Simply edit the JSON file; if hot-reload is enabled the service will refresh automatically—no restart needed.

---

## 6. Testing  

Unit tests live under `backend/design_mapper/tests/`.

```
cd backend/design_mapper
poetry run pytest
```

Key assertions:

* Style + brand precedence merges as expected  
* Tailwind class list matches snapshot  
* Hot-reload does not alter existing outputs while loading  

---

## 7. Troubleshooting  

| Symptom | Checklist |
|---------|-----------|
| 404 on `/v1/map` | Ensure `API_VERSION` env matches (`v1`) |
| Empty `tailwind_classes` | Confirm token exists in `tailwind_token_map` |
| Hot-reload not triggering | `ENABLE_HOT_RELOAD=true` and correct `MAPPINGS_FILE_PATH` |
| High latency | Disable cache only for debugging (`ENABLE_LRU_CACHE=false`) |

---

## 8. Contributing  

1. Fork / branch off `main`  
2. Add/adjust tokens in `data/mappings.json`  
3. Add tests or update snapshots  
4. Commit with scope `design_mapper:` and open PR  

Happy mapping! 🎨🖌️
