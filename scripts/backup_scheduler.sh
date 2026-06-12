#!/usr/bin/env bash
#=============================================================================
# GSM-OS Backup Scheduler
# Sets up cron jobs for automated backups.
# Usage:
#   ./scripts/backup_scheduler.sh install     # Install cron jobs
#   ./scripts/backup_scheduler.sh remove      # Remove cron jobs
#   ./scripts/backup_scheduler.sh status      # Show current cron jobs
#=============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKUP_SCRIPT="${SCRIPT_DIR}/backup.sh"
CRON_LOG="${SCRIPT_DIR}/../logs/cron_backup.log"

mkdir -p "$(dirname "${CRON_LOG}")"

install_cron() {
    echo "Installing backup cron jobs..."

    # Daily full backup at 2 AM
    local cron_daily="0 2 * * * cd ${SCRIPT_DIR}/.. && ${BACKUP_SCRIPT} >> ${CRON_LOG} 2>&1"

    # Weekly S3 sync on Sunday at 3 AM (requires --s3-bucket configured)
    local cron_weekly="0 3 * * 0 cd ${SCRIPT_DIR}/.. && ${BACKUP_SCRIPT} >> ${CRON_LOG} 2>&1"

    # Check if jobs already exist
    if crontab -l 2>/dev/null | grep -q "${BACKUP_SCRIPT}"; then
        echo "Backup cron jobs already exist. Use 'remove' first to reinstall."
        return 1
    fi

    (crontab -l 2>/dev/null; echo "${cron_daily}") | crontab -
    (crontab -l 2>/dev/null; echo "${cron_weekly}") | crontab -

    echo "Cron jobs installed:"
    echo "  Daily: 0 2 AM — Full backup"
    echo "  Weekly: Sunday 3 AM — Backup with S3 sync"
    echo "  Log: ${CRON_LOG}"
}

remove_cron() {
    echo "Removing backup cron jobs..."
    crontab -l 2>/dev/null | grep -v "${BACKUP_SCRIPT}" | crontab - || true
    echo "Backup cron jobs removed."
}

show_status() {
    echo "Current backup cron jobs:"
    echo "--------------------------"
    crontab -l 2>/dev/null | grep "${BACKUP_SCRIPT}" || echo "  No backup cron jobs configured."
    echo ""
    echo "Recent backup logs:"
    if [ -f "${CRON_LOG}" ]; then
        tail -20 "${CRON_LOG}"
    else
        echo "  No logs yet."
    fi
}

case "${1:-help}" in
    install) install_cron ;;
    remove)  remove_cron ;;
    status)  show_status ;;
    *)
        echo "Usage: $0 {install|remove|status}"
        exit 1
        ;;
esac
