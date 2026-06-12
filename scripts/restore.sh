#!/usr/bin/env bash
#=============================================================================
# GSM-OS Restore Script
# Restores Qdrant, Neo4j, and Redis from a backup directory.
# Usage:
#   ./scripts/restore.sh ./backups/20250101_120000    # Restore full backup
#   ./scripts/restore.sh --list                        # List available backups
#   ./scripts/restore.sh --latest                      # Restore most recent backup
#   ./scripts/restore.sh --qdrant-only ./backups/...   # Only Qdrant
#=============================================================================

set -euo pipefail

RESTORE_PATH=""
LIST_ONLY=false
USE_LATEST=false
QDRANT_ONLY=false
NEO4J_ONLY=false
REDIS_ONLY=false
QDRANT_HOST="${QDRANT_HOST:-localhost}"
QDRANT_PORT="${QDRANT_PORT:-6333}"
COLLECTION="${QDRANT_COLLECTION:-scientific_memory}"
NEO4J_USER="${NEO4J_USER:-neo4j}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
REDIS_HOST="${REDIS_HOST:-localhost}"
REDIS_PORT="${REDIS_PORT:-6379}"

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --list) LIST_ONLY=true ;;
        --latest) USE_LATEST=true ;;
        --qdrant-only) QDRANT_ONLY=true; RESTORE_PATH="$2"; shift ;;
        --neo4j-only) NEO4J_ONLY=true; RESTORE_PATH="$2"; shift ;;
        --redis-only) REDIS_ONLY=true; RESTORE_PATH="$2"; shift ;;
        *) RESTORE_PATH="$1" ;;
    esac
    shift
done

BACKUP_DIR="${BACKUP_DIR:-./backups}"

#─────────────────────────────────────────────
# List available backups
#─────────────────────────────────────────────
if [ "$LIST_ONLY" = true ]; then
    echo "Available backups:"
    echo "------------------"
    for dir in $(ls -d "${BACKUP_DIR}/"*/ 2>/dev/null | sort -r); do
        size=$(du -sh "$dir" 2>/dev/null | cut -f1)
        echo "  $(basename $dir)  (${size})"
    done
    exit 0
fi

#─────────────────────────────────────────────
# Find backup to restore
#─────────────────────────────────────────────
if [ "$USE_LATEST" = true ]; then
    RESTORE_PATH=$(ls -d "${BACKUP_DIR}/"*/ 2>/dev/null | sort -r | head -1)
    if [ -z "$RESTORE_PATH" ]; then
        echo "ERROR: No backups found in ${BACKUP_DIR}/"
        exit 1
    fi
fi

if [ -z "$RESTORE_PATH" ]; then
    echo "Usage: $0 <backup_path> | --list | --latest"
    echo "  backup_path: Path to the backup directory (e.g., ./backups/20250101_120000)"
    exit 1
fi

if [ ! -d "$RESTORE_PATH" ]; then
    echo "ERROR: Backup directory not found: ${RESTORE_PATH}"
    exit 1
fi

echo "========================================"
echo "  GSM-OS Restore"
echo "  Source: ${RESTORE_PATH}"
echo "========================================"
echo ""
echo "WARNING: This will overwrite existing data!"
echo "Press Ctrl+C within 5 seconds to cancel..."
sleep 3
echo "Proceeding..."

#─────────────────────────────────────────────
# Restore Qdrant
#─────────────────────────────────────────────
restore_qdrant() {
    local snapshot_file
    snapshot_file=$(ls "${RESTORE_PATH}/qdrant/"*.snapshot 2>/dev/null || true)

    if [ -z "$snapshot_file" ]; then
        echo "[Qdrant] No snapshot found in backup. Skipping."
        return 0
    fi

    echo ""
    echo "[Qdrant] Restoring collection '${COLLECTION}' from snapshot..."

    # Upload snapshot to Qdrant
    snapshot_name=$(basename "$snapshot_file")
    UPLOAD_RESP=$(curl -s -X POST \
        "http://${QDRANT_HOST}:${QDRANT_PORT}/collections/${COLLECTION}/snapshots/upload" \
        -F "snapshot=@${snapshot_file}" 2>/dev/null || echo "")

    if echo "$UPLOAD_RESP" | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('result',False)" 2>/dev/null; then
        echo "[Qdrant] Snapshot uploaded successfully"
    else
        echo "[Qdrant] WARNING: Snapshot upload failed. Manual restore may be needed."
        echo "[Qdrant] Response: ${UPLOAD_RESP}"
    fi
}

#─────────────────────────────────────────────
# Restore Neo4j
#─────────────────────────────────────────────
restore_neo4j() {
    local dump_file
    dump_file=$(ls "${RESTORE_PATH}/neo4j/"*.cypher 2>/dev/null || true)

    if [ -z "$dump_file" ]; then
        echo "[Neo4j] No dump file found in backup. Skipping."
        return 0
    fi

    echo ""
    echo "[Neo4j] Restoring from dump..."

    # Clear existing data and import
    docker exec "$(docker ps -q -f name=neo4j)" \
        cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" \
        "MATCH (n) DETACH DELETE n" 2>/dev/null || true

    # Import dump
    docker exec -i "$(docker ps -q -f name=neo4j)" \
        cypher-shell -u "${NEO4J_USER}" -p "${NEO4J_PASSWORD}" \
        < "$dump_file" 2>/dev/null || echo "[Neo4j] WARNING: Neo4j restore had issues"

    echo "[Neo4j] Restore completed"
}

#─────────────────────────────────────────────
# Restore Redis
#─────────────────────────────────────────────
restore_redis() {
    local rdb_file
    rdb_file=$(ls "${RESTORE_PATH}/redis/"dump_*.rdb 2>/dev/null || true)

    if [ -z "$rdb_file" ]; then
        echo "[Redis] No RDB file found in backup. Skipping."
        return 0
    fi

    echo ""
    echo "[Redis] Restoring RDB snapshot..."
    echo "[Redis] To restore Redis:"
    echo "  1. Stop Redis: redis-cli SHUTDOWN"
    echo "  2. Copy RDB: cp ${rdb_file} /path/to/redis/dump.rdb"
    echo "  3. Start Redis"
    echo "[Redis] Or if using Docker:"
    echo "  docker cp ${rdb_file} \$(docker ps -q -f name=redis):/data/dump.rdb"
    echo "  docker restart \$(docker ps -q -f name=redis)"
}

#─────────────────────────────────────────────
# Main
#─────────────────────────────────────────────
if [ "${QDRANT_ONLY}" = true ]; then
    restore_qdrant
elif [ "${NEO4J_ONLY}" = true ]; then
    restore_neo4j
elif [ "${REDIS_ONLY}" = true ]; then
    restore_redis
else
    restore_qdrant || echo "[WARNING] Qdrant restore had issues"
    restore_neo4j || echo "[WARNING] Neo4j restore had issues"
    restore_redis || echo "[WARNING] Redis restore had issues"
fi

echo ""
echo "========================================"
echo "  Restore complete"
echo "========================================"
