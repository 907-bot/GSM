#!/usr/bin/env bash
set -euo pipefail

echo "=== GSM-OS Health Check ==="

API_URL="${API_URL:-http://localhost:8000}"

# Check API
echo -n "API Server: "
if curl -sf "${API_URL}/health" > /dev/null 2>&1; then
    echo "OK"
else
    echo "DOWN"
    exit 1
fi

# Check Qdrant
echo -n "Qdrant: "
if curl -sf "http://localhost:6333/healthz" > /dev/null 2>&1; then
    echo "OK"
else
    echo "WARN (not checked)"
fi

# Check Neo4j
echo -n "Neo4j: "
if curl -sf "http://localhost:7474" > /dev/null 2>&1; then
    echo "OK"
else
    echo "WARN (not checked)"
fi

# Check Redis
echo -n "Redis: "
if redis-cli ping 2>/dev/null | grep -q PONG; then
    echo "OK"
else
    echo "WARN (not checked)"
fi

# Get system stats
echo ""
echo "=== System Statistics ==="
curl -sf "${API_URL}/memory/statistics" 2>/dev/null | python3 -m json.tool 2>/dev/null || echo "Unable to fetch statistics"

echo ""
echo "=== Health check complete ==="
