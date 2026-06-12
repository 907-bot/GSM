#!/usr/bin/env bash
set -euo pipefail

echo "=== GSM-OS Initialization ==="

# Check prerequisites
command -v docker >/dev/null 2>&1 || { echo "Docker is required"; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "Python 3 is required"; exit 1; }

# Create .env if missing
if [ ! -f .env ]; then
    cp .env.example .env
    echo "Created .env from .env.example — edit it with your API keys"
fi

# Install dependencies
echo "Installing Python dependencies..."
pip install -e .

# Start infrastructure
echo "Starting Docker services..."
docker compose up -d qdrant neo4j redis

# Wait for services
echo "Waiting for services..."
sleep 5

# Initialize databases
echo "Initializing databases..."
python -c "
from src.memory.episodic import EpisodicMemory
from src.memory.semantic import SemanticMemory
print('Episodic memory ready')
print('Semantic memory ready')
"

echo "=== GSM-OS initialized successfully ==="
echo "Run 'docker compose up -d' to start all services"
echo "Run 'gsm serve' to start the API"
