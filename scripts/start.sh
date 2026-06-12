#!/usr/bin/env bash
# ============================================================
# GSM-OS  —  Start Script
# ============================================================
# Usage:
#   ./scripts/start.sh            # infra + API (default)
#   ./scripts/start.sh worker     # also start Celery worker
#   ./scripts/start.sh stop       # stop everything
# ============================================================

set -euo pipefail

VENV=".venv"
PYTHON="$VENV/bin/python"
PID_FILE=".gsm_pids"

# ── Colours ───────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
ok()   { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}"; exit 1; }

# ── Stop ──────────────────────────────────────────────────
stop_all() {
    if [ -f "$PID_FILE" ]; then
        echo "Stopping GSM-OS processes..."
        while IFS= read -r pid; do
            kill "$pid" 2>/dev/null && echo "  killed PID $pid" || true
        done < "$PID_FILE"
        rm -f "$PID_FILE"
    fi
    docker-compose stop qdrant neo4j 2>/dev/null && ok "Infrastructure stopped"
    exit 0
}
[ "${1:-}" = "stop" ] && stop_all

# ── Pre-flight checks ─────────────────────────────────────
[ -f ".env" ] || err ".env not found — run: cp .env.example .env"
[ -d "$VENV" ] || err "Virtual env not found — run: /opt/homebrew/bin/python3.11 -m venv .venv && .venv/bin/pip install -e ."
$PYTHON -c "import fastapi, groq" 2>/dev/null || {
    warn "Some packages missing — installing..."
    "$VENV/bin/pip" install -e . -q
}

# ── Infrastructure ────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  GSM-OS  —  Global Scientific Memory OS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "▶  Starting infrastructure..."
docker-compose up -d qdrant neo4j 2>&1 | grep -E "(Started|Created|error|Error)" || true
ok "Qdrant  → http://localhost:6333"
ok "Neo4j   → http://localhost:7474  (user: neo4j / gsmos_password)"

# Check Redis
if redis-cli ping &>/dev/null; then
    ok "Redis   → localhost:6379  (local)"
else
    warn "Redis not running — starting Docker Redis..."
    docker-compose --profile redis up -d redis 2>&1 | tail -2
fi

# ── LLM Provider ──────────────────────────────────────────
echo ""
echo "▶  LLM Provider..."
PROVIDER=$(grep '^DEFAULT_LLM_PROVIDER' .env | cut -d= -f2)
GROQ_KEY=$(grep '^GROQ_API_KEY' .env | cut -d= -f2)

if [ "$PROVIDER" = "groq" ] && [ -n "$GROQ_KEY" ]; then
    ok "Groq    → cloud (free tier) — model: $(grep DEFAULT_LLM_MODEL .env | cut -d= -f2)"
elif command -v ollama &>/dev/null && ollama list &>/dev/null 2>&1; then
    ok "Ollama  → local (free)  — $(ollama list | tail -n +2 | awk '{print $1}' | tr '\n' ', ')"
else
    warn "No LLM configured. Options:"
    echo "  1. Groq (free): get key at https://console.groq.com/keys"
    echo "     then add GROQ_API_KEY=<key> to .env"
    echo "  2. Ollama (local): brew install ollama && ollama pull llama3"
fi

# ── API Server ────────────────────────────────────────────
echo ""
echo "▶  Starting API server..."
"$VENV/bin/uvicorn" src.api.main:app \
    --host 0.0.0.0 --port 8000 \
    --reload --log-level warning &
API_PID=$!
echo "$API_PID" > "$PID_FILE"
sleep 2

if curl -sf http://localhost:8000/health &>/dev/null; then
    ok "API     → http://localhost:8000"
    ok "Docs    → http://localhost:8000/docs"
    ok "LLM     → http://localhost:8000/llm/models"
else
    err "API failed to start. Check logs above."
fi

# ── Optional: Celery Worker ───────────────────────────────
if [ "${1:-}" = "worker" ]; then
    echo ""
    echo "▶  Starting Celery worker..."
    "$VENV/bin/celery" -A src.workers.celery_app worker -l warning -c 2 &
    WORKER_PID=$!
    echo "$WORKER_PID" >> "$PID_FILE"
    sleep 1
    ok "Worker  → running (PID $WORKER_PID)"

    "$VENV/bin/celery" -A src.workers.celery_app beat -l warning &
    BEAT_PID=$!
    echo "$BEAT_PID" >> "$PID_FILE"
    ok "Beat    → running (PID $BEAT_PID)"
fi

# ── Summary ───────────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo -e "  ${GREEN}GSM-OS is running!${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "  API:   http://localhost:8000"
echo "  Docs:  http://localhost:8000/docs"
echo "  LLMs:  http://localhost:8000/llm/models"
echo ""
echo "  Stop:  ./scripts/start.sh stop"
echo ""

wait $API_PID
