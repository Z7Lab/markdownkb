#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Clean install: ./setup.sh clean
if [ "${1:-}" = "clean" ]; then
    echo "Removing .venv..."
    rm -rf .venv
    echo "Done. Run ./setup.sh again to reinstall."
    exit 0
fi

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install --no-cache-dir -r requirements.txt

echo ""
echo "Setup complete! To activate the environment:"
echo "  source .venv/bin/activate"
echo ""
echo "To run mdkb:"
echo "  python -m app"
echo ""
echo "To use the CLI:"
echo "  python -m app.cli search \"your query\""
echo ""
echo "To wipe and reinstall from scratch:"
echo "  ./setup.sh clean && ./setup.sh"
echo ""
