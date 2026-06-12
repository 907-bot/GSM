#!/usr/bin/env bash
#=============================================================================
# GSM-OS Backup Script
# Backs up Qdrant, Neo4j, and Redis data with rotation and S3 sync.
# Usage:
#   ./scripts/backup.sh                    # Full backup
#   ./scripts/backup.sh --qdrant-only      # Only Qdrant
#   ./scripts/backup.sh --neo4j-only       # Only Neo4j
#   ./scripts/backup.sh --redis-only       # Only Redis
#   ./scripts/backup.sh --s3-bucket s3://my-bucket/backups
#   ./scripts/backup.sh --dry-run          # Show what would be backed up
#=============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_PATH="${BACKUP_DIR}/${TIMESTAMP}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
DRY_RUN=false
S3_BUCKET=""

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --qdrant-only) QDRANT_ONLY=true ;;
        --neo4j-only) NEO4J_ONLY=true ;;
        --redis-only) REDIS_ONLY=true ;;
        --s3-bucket) S3_BUCKET="$2"; shift ;;
        --dry-run) DRY_RUN=true ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
    shift
done

mkdir -p "${BACKUP_PATH}"

echo "========================================"
echo "  GSM-OS Backup — ${TIMESTAMP}"
echo "  Backup path: ${BACKUP_PATH}"
echo "========================================"

#─────────────────────────────────────────────
# Qdrant: Snapshot via API
#─────────────────────────────────────────────
backup_qdrant() {
    local QDRANT_HOST="${QDRANT_HOST:-localhost}"
    local QDRANT_PORT="${QDRANT_PORT:-6333}"
    local COLLECTION="${QDRANT_COLLECTION:-scientific_memory}"
    local SNAPSHOT_NAME="gsm_backup_${TIMESTAMP}"

    echo ""
    echo "[Qdrant] Creating snapshot of collection '${COLLECTION}'..."

    if [ "$DRY_RUN" = true ]; then
        echo "[Qdrant] DRY-RUN: Would create snapshot via API"
        echo "[Qdrant] DRY-RUN: Would download snapshot to ${BACKUP_PATH}/qdrant/"
        return 0
    fi

    # Create snapshot via Qdrant REST API
    SNAPSHOT_RESP=$(curl -s -X POST \
        "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${COLLECTION}/snapshots" \
        -H "Content-Type: application/json" 2>/dev/null || echo "")

    SNAPSHOT_NAME=$(echo "$SNAPSHOT_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('result',{}).get('name',''))" 2>/dev/null || echo "")

    if [ -z "$SNAPSHOT_NAME" ]; then
        echo "[Qdrant] WARNING: Snapshot creation failed. Check if Qdrant is running."
        echo "[Qdrant] Response: ${SNAPSHOT_RESP}"
        return 1
    fi

    echo "[Qdrant] Snapshot created: ${SNAPSHOT_NAME}"

    # Download snapshot
    mkdir -p "${BACKUP_PATH}/qdrant"
    curl -s -o "${BACKUP_PATH}/qdrant/${SNAPSHOT_NAME}" \
        "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${COLLECTION}/snapshots/${SNAPSHOT_NAME}"

    # Delete snapshot from Qdrant after download (to save server disk space)
    curl -s -X DELETE \
        "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${COLLECTION}/snapshots/${SNAPSHOT_NAME}" \
        -o /dev/null

    echo "[Qdrant] Snapshot saved to: ${BACKUP_PATH}/qdrant/${SNAPSHOT_NAME}"
}

#─────────────────────────────────────────────
# Neo4j: Dump via cypher-shell
#─────────────────────────────────────────────
backup_neo4j() {
    local NEO4J_URI="${NEO4J_URI:-bolt://localhost:7687}"
    local NEO4J_USER="${NEO4J_USER:-neo4j}"
    local NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"

    echo ""
    echo "[Neo4j] Dumping graph database..."

    if [ "$DRY_RUN" = true ]; then
        echo "[Neo4j] DRY-RUN: Would run cypher-shell dump"
        return 0
    fi

    mkdir -p "${BACKUP_PATH}/neo4j"

    # Export all nodes and relationships as Cypher statements
    docker exec "$(docker ps -q -f name=neo4j)" \
        cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" \
        "CALL apoc.export.cypher.all('/backups/neo4j_dump_${TIMESTAMP}.cypher', {format:'plain'})" \
        2>/dev/null || {

        # Fallback: simple MATCH dump via cypher-shell
        echo "[Neo4j] APOC not available, using cypher-shell dump..."
        docker exec "$(docker ps -q -f name=neo4j)" \
            cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" \
            "MATCH (n) OPTIONAL MATCH (n)-[r]->(m) RETURN n, r, m" \
            --format plain > "${BACKUP_PATH}/neo4j/neo4j_dump_${TIMESTAMP}.cypher" \
            2>/dev/null || echo "[Neo4j] WARNING: Neo4j dump failed. Is it running?"
    }

    echo "[Neo4j] Dump saved to: ${BACKUP_PATH}/neo4j/"
}

#─────────────────────────────────────────────
# Redis: RDB save and copy
#─────────────────────────────────────────────
backup_redis() {
    local REDIS_HOST="${REDIS_HOST:-localhost}"
    local REDIS_PORT="${REDIS_PORT:-6379}"

    echo ""
    echo "[Redis] Saving RDB snapshot..."

    if [ "$DRY_RUN" = true ]; then
        echo "[Redis] DRY-RUN: Would trigger BGSAVE and copy dump.rdb"
        return 0
    fi

    mkdir -p "${BACKUP_PATH}/redis"

    # Trigger save
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" BGSAVE > /dev/null 2>&1 || true
    sleep 2

    # Copy RDB from Redis container or local
    if docker ps -q -f name=redis > /dev/null 2>&1; then
        docker cp "$(docker ps -q -f name=redis)":/data/dump.rdb \
            "${BACKUP_PATH}/redis/dump_${TIMESTAMP}.rdb" 2>/dev/null || true
    fi

    # Also export config
    redis-cli -h "${REDIS_HOST}" -p "${REDIS_PORT}" CONFIG GET save \
        > "${BACKUP_PATH}/redis/redis_config_${TIMESTAMP}.txt" 2>/dev/null || true

    echo "[Redis] Backup saved to: ${BACKUP_PATH}/redis/"
}

#─────────────────────────────────────────────
# Backup paper metadata archive
#─────────────────────────────────────────────
backup_metadata() {
    echo ""
    echo "[Metadata] Backing up configuration and metadata..."

    if [ "$DRY_RUN" = true ]; then
        echo "[Metadata] DRY-RUN: Would copy configs/, .env, audit_logs/"
        return 0
    fi

    mkdir -p "${BACKUP_PATH}/configs"

    # Copy config files
    [ -d configs ] && cp -r configs "${BACKUP_PATH}/configs/" 2>/dev/null || true
    [ -f .env ] && cp .env "${BACKUP_PATH}/.env" 2>/dev/null || true
    [ -d audit_logs ] && cp -r audit_logs "${BACKUP_PATH}/audit_logs/" 2>/dev/null || true
    [ -d data/archive ] && cp -r data/archive "${BACKUP_PATH}/archived_papers/" 2>/dev/null || true

    echo "[Metadata] Configs and metadata saved"
}

#─────────────────────────────────────────────
# Retention: Clean old backups
#─────────────────────────────────────────────
rotate_backups() {
    echo ""
    echo "[Rotation] Removing backups older than ${RETENTION_DAYS} days..."

    if [ "$DRY_RUN" = true ]; then
        echo "[Rotation] DRY-RUN: Would delete backups older than ${RETENTION_DAYS} days"
        return 0
    fi

    find "${BACKUP_DIR}" -mindepth 1 -maxdepth 1 -type d -mtime "+${RETENTION_DAYS}" \
        -exec rm -rf {} \; -print 2>/dev/null || true
}

#─────────────────────────────────────────────
# S3 Sync
#─────────────────────────────────────────────
sync_to_s3() {
    if [ -z "${S3_BUCKET}" ]; then
        return 0
    fi

    echo ""
    echo "[S3] Syncing to ${S3_BUCKET}..."

    if [ "$DRY_RUN" = true ]; then
        echo "[S3] DRY-RUN: Would sync ${BACKUP_PATH} to ${S3_BUCKET}/${TIMESTAMP}/"
        return 0
    fi

    if command -v aws &>/dev/null; then
        aws s3 sync "${BACKUP_PATH}" "${S3_BUCKET}/${TIMESTAMP}/" --only-show-errors
        echo "[S3] Sync complete"
    else
        echo "[S3] WARNING: AWS CLI not found. Skipping S3 sync."
    fi
}

#─────────────────────────────────────────────
# Main
#─────────────────────────────────────────────
echo ""

if [ "${QDRANT_ONLY}" = true ]; then
    backup_qdrant
elif [ "${NEO4J_ONLY}" = true ]; then
    backup_neo4j
elif [ "${REDIS_ONLY}" = true ]; then
    backup_redis
else
    backup_qdrant || echo "[WARNING] Qdrant backup had issues (non-fatal)"
    backup_neo4j || echo "[WARNING] Neo4j backup had issues (non-fatal)"
    backup_redis || echo "[WARNING] Redis backup had issues (non-fatal)"
    backup_metadata
    rotate_backups
    sync_to_s3
fi

echo ""
echo "========================================"
echo "  Backup complete: ${BACKUP_PATH}"
echo "========================================"
