#!/usr/bin/env bash
# Update AIA-Meetings to latest version
set -euo pipefail

APP_DIR="/opt/aia-meetings"
cd "$APP_DIR"

echo "=== AIA-Meetings Update ==="
echo

# 1. Pull latest code
echo "[1/4] Pulling latest code..."
git pull origin main

# 2. Rebuild images
echo "[2/4] Rebuilding Docker images..."
docker compose build

# 3. Restart services (rolling)
echo "[3/4] Restarting services..."
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d

# 4. Cleanup
echo "[4/4] Cleaning up old images..."
docker image prune -f

echo
echo "=== Update complete ==="
docker compose ps
