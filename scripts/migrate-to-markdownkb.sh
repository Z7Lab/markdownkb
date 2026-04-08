#!/usr/bin/env bash
# Migrate existing mdkb data to markdownkb.
#
# This script handles the data directory rename and secret file rename
# that result from the mdkb → markdownkb rebrand. Run it once after
# upgrading to the markdownkb version.
#
# What it does:
#   1. Renames ~/.local/share/mdkb → ~/.local/share/markdownkb (if exists)
#   2. Renames mdkb.db → markdownkb.db inside the data directory
#   3. Renames mdkb_kg.db → markdownkb_kg.db inside the data directory
#   4. Renames secrets/mdkb_api_key → secrets/markdownkb_api_key (if exists)
#   5. Updates collection_name in config/settings.yaml
#
# What it does NOT do:
#   - Rename the ChromaDB collection (requires reindex — see note below)
#   - Update .env files (do this manually)
#
# ChromaDB collection rename:
#   The collection name changed from "mdkb" to "markdownkb". ChromaDB
#   doesn't support renaming collections, so you have two options:
#     a) Clear and reindex: make restart (the app will reindex on empty store)
#     b) Keep old name: set storage.collection_name: mdkb in settings.yaml

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo ""
echo "  MarkdownKB Migration Script"
echo "  ─────────────────────────────"
echo ""

# Detect data directory
if [ -n "${MARKDOWNKB_DATA_DIR:-}" ]; then
    DATA_DIR="$MARKDOWNKB_DATA_DIR"
elif [ -n "${MDKB_DATA_DIR:-}" ]; then
    DATA_DIR="$MDKB_DATA_DIR"
elif [ -d "$HOME/.local/share/mdkb" ]; then
    DATA_DIR="$HOME/.local/share/mdkb"
elif [ -d "$HOME/.local/share/markdownkb" ]; then
    DATA_DIR="$HOME/.local/share/markdownkb"
    echo -e "  ${GREEN}Data directory already renamed.${NC}"
else
    echo -e "  ${YELLOW}No data directory found — nothing to migrate.${NC}"
    exit 0
fi

echo "  Data directory: $DATA_DIR"
echo ""

# 1. Rename data directory
OLD_DATA="$HOME/.local/share/mdkb"
NEW_DATA="$HOME/.local/share/markdownkb"
if [ -d "$OLD_DATA" ] && [ ! -d "$NEW_DATA" ]; then
    echo -e "  ${YELLOW}Renaming data directory...${NC}"
    mv "$OLD_DATA" "$NEW_DATA"
    DATA_DIR="$NEW_DATA"
    echo -e "  ${GREEN}✓${NC} $OLD_DATA → $NEW_DATA"
elif [ -d "$OLD_DATA" ] && [ -d "$NEW_DATA" ]; then
    echo -e "  ${RED}Both $OLD_DATA and $NEW_DATA exist — skipping directory rename.${NC}"
    echo "  Please merge manually."
fi

# 2. Rename SQLite databases
if [ -f "$DATA_DIR/mdkb.db" ]; then
    mv "$DATA_DIR/mdkb.db" "$DATA_DIR/markdownkb.db"
    # Also rename WAL/SHM files if present
    [ -f "$DATA_DIR/mdkb.db-wal" ] && mv "$DATA_DIR/mdkb.db-wal" "$DATA_DIR/markdownkb.db-wal"
    [ -f "$DATA_DIR/mdkb.db-shm" ] && mv "$DATA_DIR/mdkb.db-shm" "$DATA_DIR/markdownkb.db-shm"
    echo -e "  ${GREEN}✓${NC} mdkb.db → markdownkb.db"
fi

if [ -f "$DATA_DIR/mdkb_kg.db" ]; then
    mv "$DATA_DIR/mdkb_kg.db" "$DATA_DIR/markdownkb_kg.db"
    [ -f "$DATA_DIR/mdkb_kg.db-wal" ] && mv "$DATA_DIR/mdkb_kg.db-wal" "$DATA_DIR/markdownkb_kg.db-wal"
    [ -f "$DATA_DIR/mdkb_kg.db-shm" ] && mv "$DATA_DIR/mdkb_kg.db-shm" "$DATA_DIR/markdownkb_kg.db-shm"
    echo -e "  ${GREEN}✓${NC} mdkb_kg.db → markdownkb_kg.db"
fi

# 3. Rename secret file
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
if [ -f "$PROJECT_ROOT/secrets/mdkb_api_key" ]; then
    mv "$PROJECT_ROOT/secrets/mdkb_api_key" "$PROJECT_ROOT/secrets/markdownkb_api_key"
    echo -e "  ${GREEN}✓${NC} secrets/mdkb_api_key → secrets/markdownkb_api_key"
fi

# Also check data secrets
if [ -f "$DATA_DIR/secrets/mdkb_api_key" ]; then
    mv "$DATA_DIR/secrets/mdkb_api_key" "$DATA_DIR/secrets/markdownkb_api_key"
    echo -e "  ${GREEN}✓${NC} data/secrets/mdkb_api_key → data/secrets/markdownkb_api_key"
fi

# 4. Update settings.yaml collection_name
SETTINGS="$PROJECT_ROOT/config/settings.yaml"
if [ -f "$SETTINGS" ] && grep -q "collection_name: mdkb" "$SETTINGS"; then
    sed -i 's/collection_name: mdkb/collection_name: markdownkb/' "$SETTINGS"
    echo -e "  ${GREEN}✓${NC} Updated collection_name in settings.yaml"
fi

echo ""
echo -e "  ${GREEN}Migration complete.${NC}"
echo ""
echo "  Manual steps:"
echo "    1. Update .env if you have one (MDKB_* → MARKDOWNKB_*)"
echo "    2. ChromaDB collection: clear and reindex (make restart), or"
echo "       set storage.collection_name: mdkb in settings.yaml to keep old data"
echo "    3. Docker users: rebuild (make build && make up)"
echo ""
