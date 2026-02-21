#!/usr/bin/env bash
set -euo pipefail

# Crypto Trading Desk - Standalone Setup
# For plugin mode, dependencies are handled automatically by `uv run`.
# This script is only needed when running as a standalone project (clone + run).
#
# Usage:
#   ./setup.sh          Full setup with pip + venv
#   ./setup.sh --uv     Use uv instead of pip (faster, recommended)
#   ./setup.sh --force   Force re-run even if already set up

USE_UV=false
FORCE=false
for arg in "$@"; do
    case "$arg" in
        --uv)    USE_UV=true ;;
        --force) FORCE=true ;;
    esac
done

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
VENV_PYTHON="$VENV_DIR/bin/python"
TEMPLATE="$PROJECT_DIR/.mcp.json.template"
TARGET="$PROJECT_DIR/.mcp.json"
MARKER="$PROJECT_DIR/.setup-done"

# Fast path: skip if already set up
if [ "$FORCE" = false ] && [ -f "$MARKER" ] && [ -x "$VENV_PYTHON" ]; then
    echo "Already set up. Use --force to re-run."
    exit 0
fi

echo "=== Crypto Trading Desk Setup ==="
echo "Directory: $PROJECT_DIR"
echo ""

# 1. Create virtual environment and install deps
if [ "$USE_UV" = true ]; then
    if ! command -v uv &>/dev/null; then
        echo "ERROR: uv not found. Install it: curl -LsSf https://astral.sh/uv/install.sh | sh"
        exit 1
    fi
    echo "[1/4] Installing dependencies with uv..."
    uv sync --project "$PROJECT_DIR" --quiet
    VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"
    VENV_DIR="$PROJECT_DIR/.venv"
else
    if [ ! -d "$VENV_DIR" ]; then
        echo "[1/4] Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    else
        echo "[1/4] Virtual environment exists."
    fi
    echo "      Installing dependencies with pip..."
    "$VENV_PYTHON" -m pip install --upgrade pip -q 2>&1 | tail -1 || true
    "$VENV_PYTHON" -m pip install -r "$PROJECT_DIR/requirements.txt" -q 2>&1 | tail -1 || true
fi
echo "      Done."

# 2. Generate .mcp.json from template
echo "[2/4] Generating .mcp.json..."
if [ ! -f "$TEMPLATE" ]; then
    echo "ERROR: .mcp.json.template not found!"
    exit 1
fi
sed -e "s|{{VENV_PYTHON}}|$VENV_PYTHON|g" \
    -e "s|{{PROJECT_DIR}}|$PROJECT_DIR|g" \
    "$TEMPLATE" > "$TARGET"
echo "      Done."

# 3. Create data directories + portfolio
echo "[3/4] Setting up data directories..."
mkdir -p "$PROJECT_DIR/data/trades" \
         "$PROJECT_DIR/data/reports" \
         "$PROJECT_DIR/data/logs" \
         "$PROJECT_DIR/.claude/agent-memory/portfolio-manager"

if [ ! -f "$PROJECT_DIR/data/trades/portfolio.json" ]; then
    cp "$PROJECT_DIR/data/trades/portfolio.json.example" \
       "$PROJECT_DIR/data/trades/portfolio.json"
    echo "      Created portfolio.json from example."
else
    echo "      Done."
fi

# 4. Verify MCP servers can import
echo "[4/4] Verifying MCP servers..."
ERRORS=0
for server in "$PROJECT_DIR"/mcp-servers/*.py; do
    basename=$(basename "$server")
    [ "$basename" = "validators.py" ] && continue
    if "$VENV_PYTHON" -c "import sys; sys.path.insert(0, '$PROJECT_DIR/mcp-servers'); exec(open('$server').read().split('if __name__')[0])" 2>/dev/null; then
        echo "      $basename OK"
    else
        echo "      $basename FAILED"
        ERRORS=$((ERRORS + 1))
    fi
done

# Mark setup as complete
if [ $ERRORS -eq 0 ]; then
    touch "$MARKER"
fi

echo ""
if [ $ERRORS -eq 0 ]; then
    echo "=== Setup complete! ==="
    echo ""
    echo "Next steps:"
    echo "  1. cd $PROJECT_DIR"
    echo "  2. claude"
    echo "  3. Try: /quick BTC"
    echo ""
else
    echo "=== Setup completed with $ERRORS warning(s) ==="
    echo "Some MCP servers had import issues. Run with --force to retry."
fi
