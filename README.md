# MockPilot – Real-Time AI Mock-ups from Product Conversations  
*(Repository: **CValAIAgent**)*  

MockPilot is a meeting copilot that listens to product discussions, detects UI/UX ideas _as they are spoken_, and within seconds:  

1. Generates working **React + TailwindCSS** components.  
2. Renders a live preview the team can tweak in-browser.  
3. Surfaces social-media sentiment & demographic insights about similar designs.  

> “Let’s use a hover animation like Stripe.” → A pill-button JSX snippet appears in the preview in **≤ 2 s**, plus what Gen Z & frontend devs think about it.

---

## 📚 Core Documentation  

| Topic | File |
|-------|------|
| High-level project plan | [Docs/ProjectPlan.md](Docs/ProjectPlan.md) |
| Architecture diagrams | [Docs/ArchitectureDiagram.md](Docs/ArchitectureDiagram.md) |
| API contracts | [Docs/APIContracts.md](Docs/APIContracts.md) |
| Testing strategy | [Docs/TestingStrategy.md](Docs/TestingStrategy.md) |
| Development workflow | [Docs/DevelopmentWorkflow.md](Docs/DevelopmentWorkflow.md) |
| Component implementation guide | [Docs/ComponentImplementationGuide.md](Docs/ComponentImplementationGuide.md) |
| Usage guide | [Docs/UsageGuide.md](Docs/UsageGuide.md) |

_Read the plan first, then dive into the architecture for service-level details._

---

## 🚀 Key Features

* **Live Speech-to-Text** – Uses OpenAI Whisper or Deepgram via API with VAD chunking.
* **Intent Extraction** – Regex fast-path plus GPT-4 JSON mode for design cues.  
* **AI Code Generation** – GPT-4 returns type-checked JSX validated by Babel.  
* **Sentiment Miner** – Semantic search on Reddit/Instagram via Weaviate + RoBERTa sentiment.  
* **Demographic Insights** – spaCy + rule engine tags posts by Gen Z, designers, devs, etc.  
* **Realtime Dashboard** – React 19 UI with Sandpack iframe and insight charts.  

---

## 🏗️ Repository Layout (Monorepo)

```
CValAIAgent/
├── backend/
│   ├── orchestrator/              # FastAPI WebSocket hub
│   ├── speech_to_text/            # Whisper streaming service
│   ├── intent_extractor/
│   ├── trigger_service/
│   ├── design_mapper/
│   ├── code_generator/
│   ├── sentiment_miner/
│   ├── demographic_classifier/
│   └── shared/                    # Shared config & utils
├── frontend/                      # React dashboard (Vite)
├── infra/
│   └── docker/                    # docker-compose.yml & Dockerfiles
├── data/                          # Static mapping tables, vector index
└── Docs/                          # All project documentation
```

---

## ✅ Prerequisites

* **Docker ≥ 24** (for all-in-one local dev).
* **Python 3.11** with **Poetry** (if running services natively).
* **Node 20** with **npm ≥ 9** (frontend).
* `OPENAI_API_KEY` environment variable for Whisper + GPT.

Before running any services, copy the provided environment template and fill in
your secrets:

```bash
scripts/setup_env.sh  # creates `.env` from `.env-example` if needed
# then edit `.env` to add your API keys
```
The `make dev` command (and the setup script) pass this `.env` file to
Docker Compose so your keys are loaded correctly.
Most users can leave `STT_SERVICE_WS_URL` at its default
(`ws://speech_to_text:8001/v1/stream`) which points to the speech-to-text
container when using Docker Compose.
Set `WHISPER_USE_LOCAL=true` in `.env` if you want to run Whisper locally
instead of calling the OpenAI API. Set `STT_PROVIDER=deepgram` with
`DEEPGRAM_API_KEY` if you prefer the Deepgram service.

---

## ⚡ Quick-Start (Docker Compose)

```bash
# clone repo
git clone https://github.com/AnirudhPrakashCMU/CValAIAgent.git
cd CValAIAgent

# spin up full stack (backend, redis, weaviate, frontend)
docker compose --env-file .env -f infra/docker/docker-compose.yml up --build
```

Open http://localhost:5173, allow microphone access, and say
“Let’s use a pill-shaped button with a hover bounce like Stripe.”
Watch the component and sentiment insights appear in real time!
When you hit **Stop** the recorded clip is sent to `/v1/transcribe` and its text appears under Transcripts.

---

## 🛠️ Running Services Manually

```bash
# backend example: run orchestrator
cd backend/orchestrator
poetry install
poetry run uvicorn src.main:app --reload

# frontend
cd frontend
npm ci
npm run dev  # http://localhost:5173
```

Redis & Weaviate can be started via:

```bash
docker compose -f infra/docker/docker-compose.yml up redis weaviate
```

---

## 🧪 Testing

```bash
make test          # Python unit + integration
npm run test       # React unit tests (Vitest)
make e2e           # Cypress browser tests (requires stack running)
```

Coverage reports upload to Codecov in CI.

---

## ⚙️ Continuous Integration / Deployment

* **GitHub Actions** – lint, tests, Docker build for each commit.  
* **Staging** auto-deploys `main` branch to Cloud Run (backend) & Vercel (frontend).  
* Container images published to GHCR.

---

## 🤝 Contributing

1. Review the [Development Workflow](Docs/DevelopmentWorkflow.md).  
2. Create a branch `dev/<scope>-<brief>`.  
3. Run `make lint && make test` before pushing.  
4. Update docs & add tests for new behaviour.  
5. Open a PR targeting `main`; one review required.

Happy hacking! 🎧💡🖌️
