# MockPilot Makefile

.PHONY: help bootstrap lint lint-py lint-js test test-py test-py-unit test-py-integration test-js coverage dev up down logs build clean smoke e2e docs

# Default target
help:
	@echo "MockPilot Makefile"
	@echo "------------------"
	@echo "Available targets:"
	@echo "  bootstrap          - Install dependencies and setup pre-commit hooks"
	@echo "  lint               - Run all linters (Python and JavaScript/TypeScript)"
	@echo "  lint-py            - Run Python linters (black, isort, flake8)"
	@echo "  lint-js            - Run JavaScript/TypeScript linters (ESLint)"
	@echo "  test               - Run all tests (Python and JavaScript/TypeScript)"
	@echo "  test-py            - Run all Python tests (unit and integration)"
	@echo "  test-py-unit       - Run Python unit tests"
	@echo "  test-py-integration - Run Python integration tests"
	@echo "  test-js            - Run JavaScript/TypeScript tests"
	@echo "  coverage           - Generate test coverage reports"
	@echo "  dev                - Start all services in development mode (Docker Compose with hot-reloading)"
	@echo "  up                 - Alias for 'dev'"
	@echo "  down               - Stop all services started with Docker Compose"
	@echo "  logs               - Follow logs from Docker Compose services"
	@echo "  build              - Build Docker images"
	@echo "  smoke              - Run smoke tests (minimal services, basic API calls)"
	@echo "  e2e                - Run end-to-end tests (Cypress)"
	@echo "  docs               - Open project documentation (conceptual)"
	@echo "  clean              - Clean up build artifacts and caches"

# ==============================================================================
# SETUP
# ==============================================================================
bootstrap:
	@echo "🚀 Bootstrapping MockPilot..."
	@echo "  -> Installing Python dependencies with Poetry..."
	@if command -v poetry &> /dev/null; then \
		(cd backend && poetry install --no-root); \
	else \
		echo "Poetry not found. Please install Poetry: https://python-poetry.org/docs/#installation"; \
		exit 1; \
	fi
	@echo "  -> Installing Node.js dependencies with npm..."
	@if command -v npm &> /dev/null; then \
		(cd frontend && npm ci); \
	else \
		echo "npm not found. Please install Node.js and npm: https://nodejs.org/"; \
		exit 1; \
	fi
	@echo "  -> Setting up pre-commit hooks..."
	@if command -v pre-commit &> /dev/null; then \
		pre-commit install; \
	else \
		echo "pre-commit not found. Please install pre-commit: https://pre-commit.com/#install"; \
	fi
	@echo "✅ Bootstrap complete."

# ==============================================================================
# LINTING
# ==============================================================================
lint-py:
	@echo "🔍 Linting Python code..."
	(cd backend && poetry run black . --check && poetry run isort . --check-only && poetry run flake8 .)

lint-js:
	@echo "🔍 Linting JavaScript/TypeScript code..."
	(cd frontend && npm run lint)

lint: lint-py lint-js
	@echo "✅ All linting checks passed."

# ==============================================================================
# TESTING
# ==============================================================================
test-py-unit:
	@echo "🧪 Running Python unit tests..."
	(cd backend && poetry run pytest tests/unit) # Assuming unit tests are in tests/unit

test-py-integration:
	@echo "🧪 Running Python integration tests..."
	(cd backend && poetry run pytest tests/integration) # Assuming integration tests are in tests/integration

test-py:
	@echo "🧪 Running all Python tests..."
	(cd backend && poetry run pytest)

test-js:
	@echo "🧪 Running JavaScript/TypeScript tests..."
	(cd frontend && npm run test)

test: test-py test-js
	@echo "✅ All tests passed."

coverage:
	@echo "📊 Generating Python test coverage report..."
	(cd backend && poetry run pytest --cov=./ --cov-report=xml --cov-report=html)
	@echo "Coverage report generated in backend/htmlcov/index.html and backend/coverage.xml"
	# Add JS coverage if available, e.g., (cd frontend && npm run test -- --coverage)

# ==============================================================================
# DEVELOPMENT (DOCKER COMPOSE)
# ==============================================================================
DC_FILE := infra/docker/docker-compose.yml

dev:
	@echo "🚀 Starting MockPilot development environment (Docker Compose)..."
	docker compose -f $(DC_FILE) up --build -d # -d for detached mode
	@echo "🔗 Frontend: http://localhost:5173 (Vite default)"
	@echo "🔗 Backend API (Orchestrator) might be on another port, check docker-compose logs."
	@echo "ℹ️  Run 'make logs' to see service outputs."

up: dev

down:
	@echo "🛑 Stopping MockPilot development environment..."
	docker compose -f $(DC_FILE) down

logs:
	@echo "📜 Tailing logs from Docker Compose services..."
	docker compose -f $(DC_FILE) logs -f

build:
	@echo "🏗️ Building Docker images..."
	docker compose -f $(DC_FILE) build

# ==============================================================================
# ADVANCED TESTS
# ==============================================================================
smoke:
	@echo "💨 Running smoke tests..."
	# This would typically involve spinning up minimal services and hitting key API endpoints.
	# Example: docker-compose -f $(DC_FILE) up -d redis orchestrator speech_to_text
	# Then: (cd backend && poetry run pytest tests/smoke)
	@echo "Smoke test command placeholder. Implement in backend/tests/smoke."

e2e:
	@echo "🌐 Running end-to-end tests (Cypress)..."
	# This usually requires the full stack to be running.
	# Example: make dev && (cd frontend && npm run cypress:run) or similar
	@echo "E2E test command placeholder. Ensure services are up and configure Cypress."
	(cd frontend && npm run cypress:run) # Assuming a cypress:run script in frontend/package.json

# ==============================================================================
# DOCUMENTATION
# ==============================================================================
docs:
	@echo "📚 Opening project documentation..."
	@echo "Refer to the Docs/ folder in your project."
	# For a more interactive experience, you could serve markdown files or open a specific file.
	# Example for macOS: open Docs/ProjectPlan.md
	# Example for Linux: xdg-open Docs/ProjectPlan.md
	@echo "Conceptual target: Please browse the 'Docs' directory."

# ==============================================================================
# CLEANUP
# ==============================================================================
clean:
	@echo "🧹 Cleaning up project..."
	# Python cache files
	find . -type f -name "*.py[co]" -delete
	find . -type d -name "__pycache__" -delete
	# Poetry cache (optional, can be aggressive)
	# poetry cache clear --all pypi -n
	# Node modules
	rm -rf frontend/node_modules
	# Docker cleanup (optional, can be aggressive)
	# docker system prune -af
	@echo "✅ Cleanup complete."

# Default shell for make
SHELL := /bin/bash
