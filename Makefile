.PHONY: help setup check-docker check-uv env build up down restart logs ps shell test-unit e2e clean reset-db
export PATH := /usr/local/bin:/opt/homebrew/bin:$(PATH)


## help        Print available targets (default)
help:
	echo 'Usage: make <target>'
	echo ''
	echo 'Targets:'
	grep -E '^## ' Makefile | sed 's/## /  /'

## check-docker  Verify docker daemon is reachable
check-docker:
	@command -v docker >/dev/null 2>&1 || { echo "docker not found. Open a new terminal or run: make setup"; exit 1; }
	@docker info >/dev/null 2>&1 || { echo "Docker daemon not running. Open OrbStack app."; exit 1; }

## check-uv    Verify uv is installed
check-uv:
	@command -v uv >/dev/null 2>&1 || { \
		echo "ERROR: uv is not installed."; \
		echo "Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"; \
		exit 1; \
	}

## setup       Install OrbStack and uv via brew
setup:
	@command -v brew >/dev/null 2>&1 || { echo "Install brew first"; exit 1; }
	@echo "Installing OrbStack (lightweight Docker)..."
	@brew install orbstack 2>/dev/null || true
	@echo "Installing uv..."
	@brew install uv 2>/dev/null || true
	@echo "Opening OrbStack to activate the docker CLI..."
	@open -a OrbStack 2>/dev/null || true
	@echo "Waiting for docker daemon (up to 30s)..."
	@for n in 1 2 3 4 5 6; do docker info >/dev/null 2>&1 && break; sleep 5; done
	@echo "Done. Run: make env && make up"

## env         Copy .env.example to .env if .env does not exist
env:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example."; \
		echo "ACTION REQUIRED: set OPENROUTER_API_KEY in .env"; \
	fi

## build       Build Docker images (docker compose build --pull)
build: check-docker env
	docker compose build --pull

## up          Start all services in the background
up: check-docker env build
	@docker compose up -d
	@echo ''
	@echo 'API: http://localhost:8000'

## down        Stop and remove containers
down:
	docker compose down

## restart     Stop then start all services
restart: down up

## logs        Follow logs for backend and worker
logs:
	docker compose logs -f backend worker

## ps          Show running service status
ps:
	docker compose ps

## shell       Open a bash shell inside the backend container
shell:
	docker compose exec backend bash

## test-unit   Run unit tests inside the backend container
test-unit:
	docker compose exec backend pytest tests/unit/ -v

## e2e         Run end-to-end tests locally (VPN must be OFF)
e2e:
	@echo "NOTE: VPN must be off before running E2E tests."
	python3 scripts/accelerated_e2e.py

## clean       Remove containers, volumes, and locally built images
clean:
	docker compose down -v --rmi local

## reset-db    Wipe the database and reseed from init scripts
reset-db:
	docker compose down -v
	docker compose up -d db
