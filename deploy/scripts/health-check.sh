#!/usr/bin/env bash
# AIA-Meetings health check / monitoring script
# Add to cron: */5 * * * * /opt/aia-meetings/deploy/scripts/health-check.sh
set -euo pipefail

APP_DIR="/opt/aia-meetings"
LOG_FILE="/var/log/aia-health.log"
API_URL="http://localhost:8000"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"; }

# Check API health
HTTP_CODE=$(curl -sf -o /dev/null -w '%{http_code}' "$API_URL/health" 2>/dev/null || echo "000")

if [[ "$HTTP_CODE" != "200" ]]; then
    log "ALERT: API health check failed (HTTP $HTTP_CODE)"

    # Check if containers are running
    cd "$APP_DIR"
    RUNNING=$(docker compose ps --format '{{.State}}' 2>/dev/null | grep -c "running" || echo "0")
    log "  Running containers: $RUNNING"

    if [[ "$RUNNING" -lt 4 ]]; then
        log "  Attempting restart..."
        systemctl restart aia-meetings
        sleep 10

        # Re-check
        HTTP_CODE=$(curl -sf -o /dev/null -w '%{http_code}' "$API_URL/health" 2>/dev/null || echo "000")
        if [[ "$HTTP_CODE" == "200" ]]; then
            log "  Restart successful"
        else
            log "  CRITICAL: Restart failed, manual intervention needed"
        fi
    fi
else
    # Only log every hour to avoid spam
    MINUTE=$(date +%M)
    [[ "$MINUTE" == "00" ]] && log "OK: API healthy"
fi

# Check disk space
DISK_USAGE=$(df / --output=pcent | tail -1 | tr -d ' %')
if [[ "$DISK_USAGE" -gt 85 ]]; then
    log "WARNING: Disk usage at ${DISK_USAGE}%"
fi

# Check memory
MEM_USAGE=$(free | awk '/Mem:/ {printf "%d", $3/$2 * 100}')
if [[ "$MEM_USAGE" -gt 90 ]]; then
    log "WARNING: Memory usage at ${MEM_USAGE}%"
fi
