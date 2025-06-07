#!/bin/bash
# Run repository bootstrap, intent extractor, and code generator services.
set -e

PROJECT_ROOT="$(dirname "$0")/.."
cd "$PROJECT_ROOT"

# Task 1: Repository & Tooling bootstrap
make bootstrap

# Task 3: Intent Extraction service
(cd backend/intent_extractor && poetry run uvicorn intent_extractor.main:app --reload --port 8010 &) 
INTENT_PID=$!

# Task 4: Code Generation service
(cd backend/code_generator && poetry run uvicorn code_generator.main:app --reload --port 8011 &) 
CODEGEN_PID=$!

echo "Intent Extractor running on port 8010 (pid $INTENT_PID)"
echo "Code Generator running on port 8011 (pid $CODEGEN_PID)"

trap 'kill $INTENT_PID $CODEGEN_PID' SIGINT SIGTERM
wait $INTENT_PID $CODEGEN_PID
