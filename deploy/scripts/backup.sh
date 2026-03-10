#!/usr/bin/env bash
# AIA-Meetings backup script
# Add to cron: 0 3 * * * /opt/aia-meetings/deploy/scripts/backup.sh
set -euo pipefail

APP_DIR="/opt/aia-meetings"
BACKUP_DIR="/opt/aia-backups"
RETENTION_DAYS=14
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "[$(date)] Starting backup..."

# 1. Backup PostgreSQL
echo "  Dumping database..."
docker compose -f "$APP_DIR/docker-compose.yml" exec -T db \
    pg_dump -U aia aia_meetings | gzip > "$BACKUP_DIR/db_$DATE.sql.gz"

# 2. Backup .env (encrypted)
cp "$APP_DIR/.env" "$BACKUP_DIR/env_$DATE.bak"
chmod 600 "$BACKUP_DIR/env_$DATE.bak"

# 3. Backup audio files
echo "  Backing up audio files..."
AUDIO_VOLUME=$(docker volume inspect aia-meetings_audio_data --format '{{.Mountpoint}}' 2>/dev/null || echo "")
if [[ -n "$AUDIO_VOLUME" && -d "$AUDIO_VOLUME" ]]; then
    tar czf "$BACKUP_DIR/audio_$DATE.tar.gz" -C "$AUDIO_VOLUME" . 2>/dev/null || true
fi

# 4. Cleanup old backups
echo "  Cleaning backups older than $RETENTION_DAYS days..."
find "$BACKUP_DIR" -type f -mtime +$RETENTION_DAYS -delete

# 5. Show backup sizes
echo "  Backup complete:"
ls -lh "$BACKUP_DIR"/*"$DATE"* 2>/dev/null
echo "[$(date)] Backup finished"
