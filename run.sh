#!/bin/bash
# Run mdkb locally
#
# Usage: ./run.sh [OPTIONS]
#   -d, --dev       Dev mode with hot reload (default)
#   -p, --prod      Production mode: build frontend, serve from FastAPI
#   -b, --backend   Backend only (no frontend)
#   -l, --locked    Use pinned dependencies from requirements.lock
#   -h, --help      Show this help

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

# Load .env if present (values become defaults below)
if [ -f ".env" ]; then
    set -a
    source .env
    set +a
fi

# Default settings (env vars from .env take precedence)
MODE="dev"
USE_LOCK=false
API_PORT="${API_PORT:-9713}"
FRONTEND_PORT="${FRONTEND_PORT:-9714}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# PIDs
API_PID=""
FRONTEND_PID=""

show_help() {
    echo "Usage: ./run.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  -d, --dev       Dev mode: backend + Vite dev server (default)"
    echo "  -p, --prod      Production: build frontend, serve from FastAPI"
    echo "  -b, --backend   Backend only (no frontend)"
    echo "  -l, --locked    Use pinned deps from requirements.lock"
    echo "  -h, --help      Show this help"
    echo ""
    echo "Dev mode runs:"
    echo "  Backend:  http://localhost:$API_PORT/api"
    echo "  Frontend: http://localhost:$FRONTEND_PORT (proxies /api -> backend)"
}

# Parse flags
while [[ $# -gt 0 ]]; do
    case $1 in
        -d|--dev)     MODE="dev";     shift ;;
        -p|--prod)    MODE="prod";    shift ;;
        -b|--backend) MODE="backend"; shift ;;
        -l|--locked)  USE_LOCK=true;  shift ;;
        -h|--help)    show_help;      exit 0 ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# Kill existing local processes on our ports (skip Docker containers)
cleanup_ports() {
    # Check if Docker is using the API port
    if docker ps --filter "publish=$API_PORT" --format "{{.Names}}" 2>/dev/null | grep -q .; then
        echo -e "${RED}Port $API_PORT is in use by Docker container. Stop it first (make down) or use a different port.${NC}"
        exit 1
    fi
    fuser -k $API_PORT/tcp >/dev/null 2>&1 || true
    if [ "$MODE" = "dev" ]; then
        fuser -k $FRONTEND_PORT/tcp >/dev/null 2>&1 || true
    fi
}

# Cleanup handler — kills both processes on Ctrl+C
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    [ -n "$API_PID" ]      && kill $API_PID 2>/dev/null
    [ -n "$FRONTEND_PID" ] && kill $FRONTEND_PID 2>/dev/null
    wait 2>/dev/null
    exit 0
}

# Check dependencies
check_deps() {
    # Python venv
    if [ ! -d ".venv" ]; then
        echo -e "${YELLOW}Creating Python venv...${NC}"
        python3 -m venv .venv
    fi

    # Python packages
    if ! .venv/bin/python -c "import fastapi" 2>/dev/null; then
        if [ "$USE_LOCK" = true ] && [ -f "requirements.lock" ]; then
            echo -e "${YELLOW}Installing pinned dependencies from requirements.lock...${NC}"
            .venv/bin/pip install -r requirements.lock
        else
            echo -e "${YELLOW}Installing Python dependencies...${NC}"
            .venv/bin/pip install -r requirements.txt
        fi
    fi

    # Frontend node_modules
    if [ "$MODE" != "backend" ] && [ ! -d "frontend/node_modules" ]; then
        echo -e "${YELLOW}Installing frontend dependencies...${NC}"
        cd "$PROJECT_ROOT/frontend" && npm install
        cd "$PROJECT_ROOT"
    fi
}

# ──────────────────────────────────────────────

cleanup_ports
sleep 0.3
check_deps

trap cleanup SIGINT SIGTERM

if [ "$MODE" = "backend" ]; then
    # === BACKEND ONLY ===
    echo ""
    echo -e "  ${GREEN}mdkb${NC} (backend only)"
    echo ""

    .venv/bin/python -m app.main &
    API_PID=$!

    sleep 3

    API_OK=false
    for _ in 1 2 3 4 5; do
        if curl -s "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then
            API_OK=true
            break
        fi
        sleep 1
    done

    echo ""
    if [ "$API_OK" = true ]; then
        echo -e "╔════════════════════════════════════════════╗"
        echo -e "║  ${GREEN}mdkb running${NC}                               ║"
        echo -e "╠════════════════════════════════════════════╣"
        echo -e "║  API:  ${BLUE}http://localhost:$API_PORT/api${NC}        ║"
        echo -e "╚════════════════════════════════════════════╝"
    else
        echo -e "  ${RED}Backend failed to start${NC}"
    fi
    echo ""

    wait

elif [ "$MODE" = "prod" ]; then
    # === PRODUCTION ===
    echo ""
    echo -e "  ${GREEN}mdkb${NC} (production)"
    echo ""

    # Build frontend
    if [ ! -d "frontend/dist" ] || [ "frontend/src" -nt "frontend/dist/index.html" ]; then
        echo -e "${YELLOW}Building frontend...${NC}"
        cd "$PROJECT_ROOT/frontend"
        npm run build
        cd "$PROJECT_ROOT"
    fi

    .venv/bin/python -m app.main &
    API_PID=$!

    sleep 3

    API_OK=false
    for _ in 1 2 3 4 5; do
        if curl -s "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then
            API_OK=true
            break
        fi
        sleep 1
    done

    echo ""
    if [ "$API_OK" = true ]; then
        echo -e "╔════════════════════════════════════════════╗"
        echo -e "║  ${GREEN}mdkb running${NC} (production)                 ║"
        echo -e "╠════════════════════════════════════════════╣"
        echo -e "║  App: ${BLUE}http://localhost:$API_PORT${NC}             ║"
        echo -e "║  API: ${BLUE}http://localhost:$API_PORT/api${NC}         ║"
        echo -e "╚════════════════════════════════════════════╝"
    else
        echo -e "  ${RED}Backend failed to start${NC}"
    fi
    echo ""

    wait

else
    # === DEV MODE ===
    echo ""
    echo -e "  ${GREEN}mdkb${NC} (dev mode)"
    echo ""
    echo -e "  ${YELLOW}Starting services...${NC}"
    echo ""

    # Start backend
    .venv/bin/python -m app.main 2>&1 | sed 's/^/[api] /' &
    API_PID=$!

    # Start frontend dev server
    cd "$PROJECT_ROOT/frontend"
    npm run dev 2>&1 | sed 's/^/[web] /' &
    FRONTEND_PID=$!
    cd "$PROJECT_ROOT"

    # Wait for services
    sleep 4

    API_OK=false
    for _ in 1 2 3 4 5; do
        if curl -s "http://localhost:$API_PORT/api/health" >/dev/null 2>&1; then
            API_OK=true
            break
        fi
        sleep 1
    done

    FRONTEND_OK=false
    for _ in 1 2 3; do
        if curl -s "http://localhost:$FRONTEND_PORT/" >/dev/null 2>&1; then
            FRONTEND_OK=true
            break
        fi
        sleep 1
    done

    echo ""
    if [ "$API_OK" = true ] && [ "$FRONTEND_OK" = true ]; then
        echo -e "╔════════════════════════════════════════════╗"
        echo -e "║  ${GREEN}All services running${NC}                     ║"
    else
        echo -e "╔════════════════════════════════════════════╗"
        if [ "$API_OK" = true ]; then
            echo -e "║  ${GREEN}Backend running${NC}                         ║"
        else
            echo -e "║  ${RED}Backend FAILED${NC}                           ║"
        fi
        if [ "$FRONTEND_OK" = true ]; then
            echo -e "║  ${GREEN}Frontend running${NC}                        ║"
        else
            echo -e "║  ${RED}Frontend FAILED${NC}                          ║"
        fi
    fi
    echo -e "╠════════════════════════════════════════════╣"
    echo -e "║  App: ${BLUE}http://localhost:$FRONTEND_PORT${NC}          ║"
    echo -e "║  API: ${BLUE}http://localhost:$API_PORT/api${NC}        ║"
    echo -e "╚════════════════════════════════════════════╝"
    echo ""
    echo -e "  ${YELLOW}Press Ctrl+C to stop all services${NC}"
    echo ""

    wait
fi
