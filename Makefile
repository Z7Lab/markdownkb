# mdkb — Markdown Knowledge Base
# Configuration via .env file (see .env.example)

-include .env
export

# Defaults (overridden by .env)
MDKB_CONTAINER ?= mdkb
MDKB_PORT      ?= 9713
MDKB_HOST      ?= 127.0.0.1
API_PORT        ?= 9713
FRONTEND_PORT   ?= 9714

.DEFAULT_GOAL := help
.PHONY: help install dev stop build up down restart logs ps shell clean backend prod test lint status check-ports

# ── Quick Start ──────────────────────────────────

help: ## Show this help
	@echo ""
	@echo "  mdkb — Markdown Knowledge Base"
	@echo ""
	@echo "  Usage: make <target>"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} \
		/^# ──/ { \
			gsub(/^# ── | ──+$$/, "", $$0); \
			printf "\n  \033[1m%s\033[0m\n", $$0 \
		} \
		/^[a-zA-Z_-]+:.*##/ { \
			printf "    \033[36m%-16s\033[0m %s\n", $$1, $$2 \
		}' $(MAKEFILE_LIST)
	@echo ""

install: ## Install dependencies (Python venv + npm)
	@echo "Setting up Python venv..."
	@test -d .venv || python3 -m venv .venv
	@.venv/bin/pip install -r requirements.lock
	@echo "Installing frontend dependencies..."
	@cd frontend && npm ci
	@echo "Done. Copy config: cp config/settings.yaml.example config/settings.yaml"

dev: ## Start dev servers (backend + Vite HMR)
	@./run.sh

stop: ## Stop dev servers
	@echo "Stopping dev servers..."
	@fuser -k $(API_PORT)/tcp 2>/dev/null || true
	@fuser -k $(FRONTEND_PORT)/tcp 2>/dev/null || true
	@echo "Done."

# ── Docker ───────────────────────────────────────

build: ## Build Docker image
	@docker compose build

up: ## Start container (detached)
	@docker compose up -d
	@echo ""
	@echo "  mdkb running at http://localhost:$(MDKB_PORT)"
	@echo "  Logs: make logs"
	@echo ""

down: ## Stop container
	@docker compose down

restart: ## Restart container
	@docker compose restart

logs: ## Tail container logs
	@docker compose logs -f

ps: ## Show container status
	@docker compose ps

shell: ## Open a shell in the container
	@docker compose exec mdkb /bin/bash

clean: ## Stop container and remove image
	@docker compose down --rmi local --volumes
	@echo "Cleaned up containers and images."

# ── Development ──────────────────────────────────

backend: ## Start backend only (no frontend)
	@./run.sh --backend

prod: ## Production mode (build frontend + serve)
	@./run.sh --prod

test: ## Run pytest suite
	@.venv/bin/pytest tests/

lint: ## Run pylint
	@.venv/bin/pylint app/

# ── Utilities ────────────────────────────────────

status: ## Show dev server and Docker status
	@echo ""
	@echo "  Dev servers:"
	@if fuser $(API_PORT)/tcp 2>/dev/null | grep -q .; then \
		echo "    Backend  (port $(API_PORT)):    \033[32mrunning\033[0m"; \
	else \
		echo "    Backend  (port $(API_PORT)):    \033[31mstopped\033[0m"; \
	fi
	@if fuser $(FRONTEND_PORT)/tcp 2>/dev/null | grep -q .; then \
		echo "    Frontend (port $(FRONTEND_PORT)): \033[32mrunning\033[0m"; \
	else \
		echo "    Frontend (port $(FRONTEND_PORT)): \033[31mstopped\033[0m"; \
	fi
	@echo ""
	@echo "  Docker:"
	@docker compose ps 2>/dev/null || echo "    Not running"
	@echo ""

check-ports: ## Check if ports are available
	@echo "Checking ports..."
	@if fuser $(API_PORT)/tcp 2>/dev/null | grep -q .; then \
		echo "  Port $(API_PORT): \033[31min use\033[0m (PID: $$(fuser $(API_PORT)/tcp 2>/dev/null))"; \
	else \
		echo "  Port $(API_PORT): \033[32mavailable\033[0m"; \
	fi
	@if fuser $(FRONTEND_PORT)/tcp 2>/dev/null | grep -q .; then \
		echo "  Port $(FRONTEND_PORT): \033[31min use\033[0m (PID: $$(fuser $(FRONTEND_PORT)/tcp 2>/dev/null))"; \
	else \
		echo "  Port $(FRONTEND_PORT): \033[32mavailable\033[0m"; \
	fi
	@if fuser $(MDKB_PORT)/tcp 2>/dev/null | grep -q .; then \
		echo "  Port $(MDKB_PORT) (Docker): \033[31min use\033[0m"; \
	else \
		echo "  Port $(MDKB_PORT) (Docker): \033[32mavailable\033[0m"; \
	fi
