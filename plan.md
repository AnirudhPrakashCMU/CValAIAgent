# Plan for Real-Time Web Mockup Generator

This document outlines the steps to build a system that listens to product conversations and instantly produces visual prototypes.

## 1. Goals
1. Listen to an ongoing discussion (speech audio).
2. Detect when a speaker describes a web UI concept or implementation idea.
3. Generate a quick CSS/JavaScript mockup to visualize the idea.
4. Display the mockup in a browser so the team can iterate rapidly.

## 2. High-Level Architecture
- **Speech-to-Text Service** – streams audio to a transcription engine (e.g., OpenAI Whisper).
- **Intent Detector** – analyses transcripts for phrases that mention UI or design changes.
- **Code Generator** – given an intent, produces a simplified snippet (HTML/CSS/JS or JSX) illustrating the design.
- **Frontend Preview** – React/Tailwind interface that shows the transcript and hot‑reloads the generated snippet.
- **Message Bus** – Redis Pub/Sub or WebSockets used to pass messages between components with sub‑second latency.

## 3. Implementation Tasks
1. **Repository & Tooling**
   - Initialize Git repository and set up linting/formatting (Black, ESLint, Prettier).
   - Add Docker Compose with services for the backend, Redis and frontend.
   - Create Makefile scripts for `make dev`, `make lint`, and `make test`.

2. **Speech Transcription**
   - Implement a WebSocket endpoint that accepts audio chunks (16‑kHz PCM or Opus).
   - Stream audio to a Whisper model (local or API) and return interim/final transcripts in JSON.
   - Publish final transcripts to a Redis channel `transcripts`.

3. **Intent Extraction**
   - Consume transcript messages and detect when a design‑related idea is mentioned.
   - Start with regex triggers (e.g., “button”, “hover”, “modal”) and expand with a small GPT prompt for edge cases.
   - Produce a structured intent payload (`{component: "button", style: "pill"}`) on channel `intents`.

4. **Code Generation**
   - Map intents to simple design tokens or known patterns (e.g., pill button → Tailwind classes).
   - Use GPT or templates to render a short HTML/CSS/JS snippet.
   - Validate the snippet with a JS/TS parser to ensure it doesn’t break the preview.
   - Publish the snippet to channel `components`.

5. **Frontend Preview**
   - Build a React app that connects via WebSocket to receive transcripts and code snippets.
   - Display the live transcript in a side panel.
   - Inject or hot‑reload the latest code snippet into an iframe or Sandpack area so the team can see the result immediately.

6. **Orchestration & Triggering**
   - Add a small service that listens to both `transcripts` and `intents` and decides when to request code generation (e.g., debounce when multiple similar ideas are detected).
   - Expose a REST endpoint `/generate` that the trigger service calls with the current intent.

7. **Testing & QA**
   - Unit tests for each service (transcription, intent detection, code generation).
   - Integration tests that feed sample audio and assert that a snippet appears in the frontend.
   - End‑to‑end test using a recorded conversation to verify latency stays under 2s from speech to preview.

8. **Deployment**
   - Dockerfiles for backend services and the frontend.
   - GitHub Actions workflow to lint, test and build images on every push.
   - Optional: deploy to a staging environment (e.g., Cloud Run + Vercel).

## 4. Milestones
1. **Bootstrap** – Repo initialized, Docker Compose up, CI passing.
2. **Transcription MVP** – WebSocket audio streaming with transcripts sent to frontend.
3. **Intent Detection** – Basic rules + GPT fallback capturing design ideas.
4. **Code Generation Prototype** – Simple component snippets produced and rendered.
5. **Full Demo** – All services wired together with a live browser preview.
6. **Polish** – Improved prompting, better UI, and sentiment/analytics extensions.

