# Development Workflow – MockPilot  
*(Docs/DevelopmentWorkflow.md – v1.0 • 2025-05-31)*  

This document prescribes **how we build, test, review, and ship** MockPilot.  
It complements `ProjectPlan.md` (what we build) and `TestingStrategy.md` (how we prove it works).

---

## 1. Guiding Principles  

1. **Fast feedback** – every push runs lint + unit tests < 5 min.  
2. **Incremental delivery** – ship thin vertical slices; demo-able at all times.  
3. **Code health > feature speed** – lint, type, and test gates are non-negotiable.  
4. **Docs are code** – update `Docs/` in the same PR when behaviour or API changes.  

---

## 2. Branching Strategy  

| Branch | Purpose | Protection Rules |
|--------|---------|------------------|
| `main` | Always deployable; auto-deploy to **staging** | PR merge only, 1 review, CI green |
| `release/*` | Cut candidate releases (`release/v1.1`) | Same as `main`; tag on merge |
| `dev/*` | Feature / fix branches (`dev/stt-stream`) | No direct pushes if shared |
| `hotfix/*` | Emergency prod patch | CI fast-track, still via PR |

### 2.1  Creating a Feature Branch  

```bash
git checkout -b dev/<scope>-<brief>
#   scope examples: stt, intent, frontend, docs, infra
```

Delete branches after merge to keep the graph clean.

---

## 3. Commit & Pull-Request Conventions  

### 3.1  Commit Message Format  

```
<scope>: <imperative summary> (#[issue])
```

Examples:  
`stt: add Whisper streaming wrapper (#12)`  
`frontend: fix dark-mode toggle`

### 3.2  Pull-Request Checklist  

Every PR **must**:  

- [ ] Reference an open issue or roadmap ID (`closes #45`)  
- [ ] Pass `make lint` and `make test` locally  
- [ ] Update docs / API contracts if behaviour changes  
- [ ] Bump `schema_version` when editing message models  
- [ ] Add or update relevant tests (unit, integration, UI)  
- [ ] Include screenshots/GIFs for UI changes  
- [ ] Obtain at least **one reviewer approval**  

Labels: `scope/*`, `type/feat|bug|chore|docs`, `size/XS-XL`.

---

## 4. Testing Requirements per PR  

| Test Layer | Mandatory? | How to run |
|------------|------------|-----------|
| Lint / Static | ✅ | `make lint` |
| Unit | ✅ | `make test-py-unit` & `npm run test` |
| Integration | If touching service boundaries | `make test-py-integration` |
| UI / Cypress | If frontend affected | `make e2e` |
| Load / k6 | If perf-sensitive change | `make smoke` (light) or nightly pipeline |

Coverage gates enforced in CI: **Python ≥ 90 %**, **TS/TSX ≥ 85 %**.

---

## 5. Continuous Integration & Deployment  

### 5.1  GitHub Actions Workflow  

```
name: CI

on: [push, pull_request]

jobs:
  lint-test:
    runs-on: ubuntu-latest
    steps:                   # abbreviated
      - uses: actions/checkout@v4
      - run: make lint
      - run: make test
    # uploads coverage to Codecov

  docker-build:
    if: github.ref == 'refs/heads/main'
    needs: lint-test
    runs-on: ubuntu-latest
    steps:
      - checkout
      - run: docker compose -f infra/docker/docker-compose.yml build
      - run: docker compose push
      - run: echo "Trigger Cloud Run + Vercel deploy"
```

Matrix strategy spins separate jobs for **backend**, **frontend** to parallelise.

### 5.2  Environments  

| Env | Branch | URL | Notes |
|-----|--------|-----|-------|
| Local | any | `localhost` | `make dev` (docker-compose hot reload) |
| Staging | `main` | `stg.mockpilot.app` | Auto-deploy; smoke tests |
| Production | tag `v*.*.*` | `mockpilot.app` | Manual approval; blue-green |

Rollback = redeploy previous tag.

---

## 6. Release Process  

1. Finish milestone; merge all feature branches.  
2. `git checkout main && git pull`.  
3. `npm run version` / bump `pyproject.toml` as needed.  
4. `git checkout -b release/vX.Y.Z && git push`.  
5. Open PR → QA smoke + load tests.  
6. Tag (`vX.Y.Z`) on merge; GitHub Actions builds images, pushes to registry, deploys to **prod**.  
7. Announce in `CHANGELOG.md` and Slack **#mockpilot-dev** channel.

Hotfix: branch off tagged commit into `hotfix/*`, bump patch, repeat.

---

## 7. Local Development Cheatsheet  

```bash
make bootstrap   # poetry + npm + pre-commit
make dev         # docker-compose up with live reload
make lint        # all linters
make test        # unit + integration
make e2e         # Cypress headless
make coverage    # open htmlcov/index.html
make docs        # open Docs/ tree
```

To run a single backend service natively:

```bash
cd backend/speech_to_text
poetry run uvicorn main:app --reload
```

Frontend hot reload:

```bash
cd frontend
npm run dev          # http://localhost:5173
```

---

## 8. Code Review Guidelines for Reviewers  

1. **Correctness first** – logic, edge cases, error handling.  
2. **Security** – JWT handling, sanitisation, rate-limits.  
3. **Performance** – unnecessary DB/LLM calls, N+1 loops.  
4. **Readability** – names, comments, docstrings, TypeScript types.  
5. **Tests** – cover new code paths, negative cases.  
6. **Docs** – updated where applicable.  

Use **GitHub suggestions** for minor fixes; request changes for bigger issues.

---

## 9. Continuous Improvement  

- **Retrospective** at each milestone; file notes under `Docs/retros/`.  
- **RFC process** (`Docs/rfcs/RFC-xxxx.md`) for large architectural shifts.  
- **Tech debt tickets** labelled `debt` with severity; triaged weekly.  

---

## 10. Communication  

| Channel | Purpose |
|---------|---------|
| Slack `#mockpilot-dev` | Day-to-day chat, pairing calls |
| GitHub Issues | Task tracking, bugs, roadmap |
| Stand-up (async) | Daily thread in Slack |
| Demo video | Post milestone demos to Slack & repo Wiki |

---

### Change Log  

| Date | Version | Author | Summary |
|------|---------|--------|---------|
| 2025-05-31 | 1.0 | Anirudh | Initial development workflow |
