#!/bin/bash
# Launch the financial calculator web UI
# Usage: ./launch_ui.sh [port]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
PORT="${1:-5050}"

cd "$SKILL_DIR"

# Check if venv exists, create if not
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    venv/bin/pip install flask --quiet
fi

# Launch the web UI
echo ""
echo "🧮 Financial Calculator"
echo "📊 Open: http://localhost:$PORT"
echo "Press Ctrl+C to stop"
echo ""

venv/bin/python scripts/web_ui.py "$PORT"
