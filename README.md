# Global Scientific Memory OS (GSM-OS)

A continuous scientific discovery and bottleneck detection platform.

## Quick Start

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"
docker compose up -d qdrant neo4j redis
gsm serve
```

## Architecture

- **Episodic Memory**: Qdrant vector database for paper/finding storage
- **Semantic Memory**: Neo4j graph database for concept relationships
- **Research Agents**: Domain-specific agents monitoring arXiv, PubMed, Semantic Scholar
- **Engines**: Replay, Contradiction, Bottleneck, Hypothesis, Graph Discovery
- **Task Queue**: Celery + Redis for scheduled processing
- **Frontend**: React + TypeScript + Tailwind dashboard
