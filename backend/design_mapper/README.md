# Design Mapper Service – MockPilot  
*(backend/design_mapper)*  

Translates **brand references** (e.g. `stripe`, `apple`) and **style cues** (e.g. `hover_lift`, `pill_button`) into:

* **Theme tokens** – an abstract, design-system friendly representation.  
* **Tailwind CSS utility classes** – concrete classes rendered to the frontend preview.

It is 100 % deterministic (no LLMs) and hot-reloads `mappings.json` at runtime, making it the single source of truth for design semantics inside MockPilot.

---

## 1. Directory Layout  

```
backend/design_mapper/
├── Dockerfile
├── pyproject.toml
├── run_service.sh
└── src/design_mapper/
    ├── api.py           # FastAPI endpoints
    ├── config.py        # Pydantic settings (env-driven)
    ├── service/mapper.py
    ├── models/schemas.py
    └── utils/loader.py  # file watcher, hot reload
```

---

## 2. Configuration  

All settings are environment-variable driven (see `config.py`).  

| Variable | Default | Description |
|----------|---------|-------------|
| `MAPPINGS_FILE_PATH` | `data/mappings/mappings.json` | Absolute/relative path to the JSON mapping table. |
| `ENABLE_HOT_RELOAD` | `true` | Watch the file and auto-reload when it changes. |
| `FILE_WATCH_INTERVAL_SECONDS` | `2.0` | Polling interval for the watchdog observer. |
| `ENABLE_LRU_CACHE` | `true` | Cache identical mapping requests (size = `LRU_CACHE_MAXSIZE`). |
| `LOG_LEVEL` | `INFO` | Standard Python logging level. |
| `API_VERSION` | `v1` | URL prefix for all REST routes. |
| `API_PORT` | `8002` | Container / local listening port. |

---

## 3. Running the Service  

### 3.1 Via Docker (recommended)  

```bash
# From repo root
docker compose -f infra/docker/docker-compose.yml up design_mapper
# or standalone:
docker build -t mockpilot-design-mapper backend/design_mapper
docker run -p 8002:8002 -v $PWD/data/mappings:/data/mappings mockpilot-design-mapper
```

### 3.2 Locally with Poetry  

```bash
cd backend/design_mapper
poetry install
poetry run uvicorn design_mapper.api:app --reload --port 8002
```

Hot-reload of both Python code (`--reload`) and `mappings.json` will now work.

---

## 4. REST API Reference  

All paths are prefixed with `/<API_VERSION>` (`/v1` by default).

| Method | Path | Purpose |
|--------|------|---------|
| **POST** | `/v1/map` | Map brands & styles → theme tokens + Tailwind classes. |
| **POST** | `/v1/reload` | Force re-load of mapping file & clear caches. |
| **GET** | `/v1/healthz` | Service health and mapping stats. |

### 4.1 POST /v1/map  

**Request body (`application/json`)**

```json
{
  "styles": ["hover_lift", "pill_button"],
  "brand_refs": ["stripe"],
  "component": "button"
}
```

**Sample response**

```json
{
  "theme_tokens": {
    "primary_color_scheme": "blue-purple-gradient",
    "button_style": "rounded-md",
    "animation_ease": "ease-out-sine",
    "font_family": "sans-serif",
    "text_color_primary": "white",
    "border_subtle": "border-transparent",
    "border_radius": "full",
    "padding_x": "px-6",
    "padding_y": "py-2",
    "interaction": "transform transition-transform duration-150 hover:scale-105 hover:shadow-lg"
  },
  "tailwind_classes": [
    "bg-gradient-to-r",
    "from-blue-500",
    "to-purple-600",
    "rounded-md",
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

### 4.2 POST /v1/reload  

Reloads the file **and** clears the LRU cache.

```bash
curl -X POST http://localhost:8002/v1/reload
```

Returns `{ "status": "success", "message": "Mappings reloaded successfully" }`.

### 4.3 GET /v1/healthz  

```bash
curl http://localhost:8002/v1/healthz
```

```json
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

## 5. Mapping File Schema (`mappings.json`)  

```jsonc
{
  "brands":      { "<brand_id>": { /* token overrides */ } },
  "styles":      { "<style_id>": { /* token overrides */ } },
  "tailwind_token_map": { "<abstract_token>": "<tailwind_class>" }
}
```

**Precedence order**

1. _Style_ properties override _brand_ properties if keys overlap.  
2. Latest item in list wins (order in request matters).  
3. Defaults in `ThemeTokens` remain if untouched.

Add new brands or styles by editing `data/mappings/mappings.json`; the service will hot-reload automatically.

---

## 6. Usage in Other Services  

Python example (inside Trigger Service):

```python
import httpx

async def map_design_tokens(styles, brands):
    async with httpx.AsyncClient(base_url="http://design_mapper:8002") as client:
        resp = await client.post("/v1/map", json={"styles": styles, "brand_refs": brands})
        resp.raise_for_status()
        return resp.json()
```

---

## 7. Testing the Mapper  

Unit tests live in `backend/design_mapper/tests/`. Run all tests:

```bash
cd backend/design_mapper
poetry run pytest
```

Key assertions:
* Style + brand precedence merges as expected.
* Tailwind class list matches snapshot.
* Hot-reload does not alter existing outputs while loading.

---

## 8. Troubleshooting  

| Symptom | Checklist |
|---------|-----------|
| **404 Not Found** on `/v1/map` | Ensure `API_VERSION` env var matches (`v1`). |
| Empty `tailwind_classes` | Check `tailwind_token_map` contains the needed abstract tokens. |
| Hot-reload not triggering | Verify `ENABLE_HOT_RELOAD=true` and path in `MAPPINGS_FILE_PATH` is correct. |
| High latency | Disable `ENABLE_LRU_CACHE=false` only for debugging; otherwise cache results. |

---

## 9. Extending / Contributing  

1. Edit `data/mappings/mappings.json` and add your tokens.  
2. Update unit tests & snapshots.  
3. Commit & open PR (see root **Development Workflow**).  

Enjoy mapping! 🎨🖌️  
