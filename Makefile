# MarkdownKB — Markdown Knowledge Base
# Configuration via .env file (see .env.example)

-include .env
export

# Defaults (overridden by .env)
MARKDOWNKB_CONTAINER ?= markdownkb
MARKDOWNKB_PORT      ?= 9713
MARKDOWNKB_MCP_PORT  ?= 9715
MARKDOWNKB_HOST      ?= 127.0.0.1
API_PORT        ?= 9713
FRONTEND_PORT   ?= 9714

.DEFAULT_GOAL := help
.PHONY: help install dev stop docker-build docker-rebuild docker-build-full docker-rebuild-full docker-up docker-down docker-restart docker-logs docker-ps docker-shell docker-clean docker-clean-all backend prod test lint status check-ports mcp audit typecheck

# ── Quick Start ──────────────────────────────────

help: ## Show this help
	@echo ""
	@echo "  MarkdownKB — Markdown Knowledge Base"
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
	@echo "  \033[1mWhen to use what\033[0m"
	@echo "    .env changes (ports, keys, bind)     docker-down && docker-up"
	@echo "    Config files (mounted volumes)       docker-restart"
	@echo "    Code changes (app/, frontend/)       docker-build (base) / docker-build-full (full)"
	@echo "    Dependency changes (requirements,    docker-rebuild / docker-rebuild-full"
	@echo "      package-lock.json)"
	@echo "    No changes — just start the app      docker-up"
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

docker-build: ## Build image (cached) + restart — use after code changes
	@docker compose build
	@docker compose up -d

docker-rebuild: ## Full clean rebuild (no cache) + restart — use after dependency changes only
	@docker compose build --no-cache
	@docker compose up -d

# NOTE: explicit -f flags suppress Docker Compose's auto-loading of compose.override.yml,
# so compose.override.yml (source directory mounts) must be listed explicitly here.
# Omitting it causes sources to appear unmounted → scanner prunes all indexed files.
docker-build-full: ## Build 'full' image variant (includes YouTube transcript extraction) + restart
	@docker compose -f compose.yml -f compose.override.yml -f compose.full.yml build
	@docker compose -f compose.yml -f compose.override.yml -f compose.full.yml up -d

docker-rebuild-full: ## Full clean rebuild of 'full' variant (no cache) + restart
	@docker compose -f compose.yml -f compose.override.yml -f compose.full.yml build --no-cache
	@docker compose -f compose.yml -f compose.override.yml -f compose.full.yml up -d


docker-up: ## Start container (detached)
	@mkdir -p data/chromadb data/plans
	@touch config/compose.override.yml
	@docker compose up -d
	@echo ""
	@echo "  MarkdownKB running at http://localhost:$(MARKDOWNKB_PORT)"
	@echo "  MCP server at   http://localhost:$(MARKDOWNKB_MCP_PORT)/mcp"
	@LAN_IP=$$(hostname -I 2>/dev/null | awk '{print $$1}'); \
	LAN_HOST=$$(hostname 2>/dev/null); \
	if [ -n "$$LAN_IP" ]; then \
		echo "  Network:        http://$$LAN_IP:$(MARKDOWNKB_PORT)"; \
		echo "  MCP network:    http://$$LAN_IP:$(MARKDOWNKB_MCP_PORT)/mcp"; \
	fi; \
	if [ -n "$$LAN_HOST" ]; then \
		echo "                  http://$$LAN_HOST.local:$(MARKDOWNKB_PORT)"; \
	fi
	@echo "  Logs: make docker-logs"
	@echo ""

docker-down: ## Stop container
	@docker compose down

docker-restart: ## Restart container
	@docker compose restart

docker-logs: ## Tail container logs
	@docker compose logs -f

docker-ps: ## Show container status
	@docker compose ps

docker-shell: ## Open a shell in the container
	@docker compose exec markdownkb /bin/bash

docker-clean: ## Stop container and remove image (preserves data volumes)
	@docker compose down --rmi local
	@echo "Cleaned up containers and images (data volumes preserved)."

docker-clean-all: ## Stop container, remove image AND data volumes (destructive — re-index required)
	@echo "WARNING: This will destroy all indexed data, plans, and plugins."
	@printf "Are you sure? [y/N] " && read ans && [ "$${ans:-N}" = "y" ]
	@docker compose down --rmi local --volumes
	@echo "Cleaned up containers, images, and volumes."

# ── Development ──────────────────────────────────

backend: ## Start backend only (no frontend)
	@./run.sh --backend

mcp: ## Start MCP server locally (Streamable HTTP on port 9715)
	@.venv/bin/python mcp_server.py --http --port $(MARKDOWNKB_MCP_PORT)

prod: ## Production mode (build frontend + serve)
	@./run.sh --prod

test: ## Run pytest suite (with coverage)
	@.venv/bin/pytest tests/

lint: ## Run pylint
	@.venv/bin/pylint app/

typecheck: ## Run mypy static type checker
	@.venv/bin/mypy app/

audit: ## Scan locked runtime deps for known CVEs (pip-audit)
	@.venv/bin/pip-audit -r requirements.lock --strict

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
	@if fuser $(MARKDOWNKB_PORT)/tcp 2>/dev/null | grep -q .; then \
		echo "  Port $(MARKDOWNKB_PORT) (Docker): \033[31min use\033[0m"; \
	else \
		echo "  Port $(MARKDOWNKB_PORT) (Docker): \033[32mavailable\033[0m"; \
	fi
	@if fuser $(MARKDOWNKB_MCP_PORT)/tcp 2>/dev/null | grep -q .; then \
		echo "  Port $(MARKDOWNKB_MCP_PORT) (MCP):    \033[31min use\033[0m"; \
	else \
		echo "  Port $(MARKDOWNKB_MCP_PORT) (MCP):    \033[32mavailable\033[0m"; \
	fi
