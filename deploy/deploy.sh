#!/usr/bin/env bash
#
# AIA-Meetings — Full server deployment script for Ubuntu 22.04/24.04
# Usage: scp -r . user@server:/opt/aia-meetings && ssh user@server 'cd /opt/aia-meetings && sudo bash deploy/deploy.sh'
#
set -euo pipefail

# ── Colors ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log()  { echo -e "${GREEN}[✓]${NC} $*"; }
warn() { echo -e "${YELLOW}[!]${NC} $*"; }
err()  { echo -e "${RED}[✗]${NC} $*"; exit 1; }

# ── Check root ──────────────────────────────────────────────────────
[[ $EUID -eq 0 ]] || err "Run as root: sudo bash deploy/deploy.sh"

# ── Variables ───────────────────────────────────────────────────────
APP_DIR="/opt/aia-meetings"
APP_USER="aia"
DOMAIN="${DOMAIN:-}"

echo "============================================="
echo "  AIA-Meetings Deployment"
echo "============================================="
echo

# ── Ask for domain if not set ───────────────────────────────────────
if [[ -z "$DOMAIN" ]]; then
    read -rp "Enter domain name (or leave empty for IP-only): " DOMAIN
fi

# ── 1. System packages ─────────────────────────────────────────────
log "Updating system packages..."
apt-get update -qq
apt-get install -y -qq \
    curl wget git ufw fail2ban \
    ca-certificates gnupg lsb-release \
    nginx certbot python3-certbot-nginx \
    > /dev/null 2>&1
log "System packages installed"

# ── 2. Install Docker ──────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
    log "Installing Docker..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
        gpg --dearmor -o /etc/apt/keyrings/docker.gpg 2>/dev/null
    chmod a+r /etc/apt/keyrings/docker.gpg

    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | \
        tee /etc/apt/sources.list.d/docker.list > /dev/null

    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin > /dev/null 2>&1
    systemctl enable --now docker
    log "Docker installed"
else
    log "Docker already installed"
fi

# ── 3. Create app user ─────────────────────────────────────────────
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/bash -m -d /home/$APP_USER $APP_USER
    usermod -aG docker $APP_USER
    log "User '$APP_USER' created"
else
    usermod -aG docker $APP_USER
    log "User '$APP_USER' exists"
fi

# ── 4. Setup app directory ─────────────────────────────────────────
mkdir -p "$APP_DIR"
if [[ "$(pwd)" != "$APP_DIR" ]]; then
    cp -r . "$APP_DIR/"
fi
chown -R $APP_USER:$APP_USER "$APP_DIR"
log "App files in $APP_DIR"

# ── 5. Environment file ────────────────────────────────────────────
if [[ ! -f "$APP_DIR/.env" ]]; then
    cp "$APP_DIR/.env.example" "$APP_DIR/.env"
    # Generate random secret key
    SECRET=$(openssl rand -hex 32)
    sed -i "s|change-me-to-random-string|$SECRET|" "$APP_DIR/.env"
    # Fix DB URL for docker network
    sed -i "s|localhost:5432|db:5432|" "$APP_DIR/.env"
    sed -i "s|localhost:6379|redis:6379|" "$APP_DIR/.env"
    warn ".env created — edit $APP_DIR/.env with your API keys:"
    warn "  - YANDEX_API_KEY"
    warn "  - YANDEX_FOLDER_ID"
    warn "  - ANTHROPIC_API_KEY"
    warn "  - TELEGRAM_BOT_TOKEN"
    chmod 600 "$APP_DIR/.env"
else
    log ".env already exists"
fi

# ── 6. Docker Compose production override ───────────────────────────
cat > "$APP_DIR/docker-compose.prod.yml" << 'YAML'
# Production overrides
services:
  api:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          memory: 512M

  worker:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          memory: 1G

  bot:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          memory: 256M

  db:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          memory: 512M

  redis:
    restart: always
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    deploy:
      resources:
        limits:
          memory: 256M
YAML
log "Production compose override created"

# ── 7. Firewall (additive — safe for multi-app servers) ────────────
log "Configuring firewall..."
ufw default deny incoming > /dev/null 2>&1
ufw default allow outgoing > /dev/null 2>&1
ufw allow ssh > /dev/null 2>&1
ufw allow 80/tcp > /dev/null 2>&1
ufw allow 443/tcp > /dev/null 2>&1
ufw --force enable > /dev/null 2>&1
log "Firewall configured (SSH, HTTP, HTTPS — existing rules preserved)"

# ── 8. Nginx ───────────────────────────────────────────────────────
log "Configuring Nginx..."

if [[ -n "$DOMAIN" ]]; then
    cat > /etc/nginx/sites-available/aia-meetings << NGINX
server {
    listen 80;
    server_name $DOMAIN;

    # Let's Encrypt challenge
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }

    location / {
        return 301 https://\$host\$request_uri;
    }
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    # SSL will be configured by certbot
    ssl_certificate /etc/ssl/certs/ssl-cert-snakeoil.pem;
    ssl_certificate_key /etc/ssl/private/ssl-cert-snakeoil.key;

    client_max_body_size 500M;

    # Security headers
    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;
    add_header X-XSS-Protection "1; mode=block" always;
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection "upgrade";

        # Timeouts for large file uploads
        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }
}
NGINX
else
    cat > /etc/nginx/sites-available/aia-meetings << 'NGINX'
server {
    listen 80;
    server_name _;

    client_max_body_size 500M;

    add_header X-Content-Type-Options nosniff always;
    add_header X-Frame-Options DENY always;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        proxy_connect_timeout 300;
        proxy_send_timeout 300;
        proxy_read_timeout 300;
    }
}
NGINX
fi

ln -sf /etc/nginx/sites-available/aia-meetings /etc/nginx/sites-enabled/
# Only remove default if no other apps depend on it
if [[ ! -f /etc/nginx/sites-available/default-custom ]]; then
    rm -f /etc/nginx/sites-enabled/default
fi
nginx -t && systemctl reload nginx
log "Nginx configured"

# ── 9. SSL Certificate ─────────────────────────────────────────────
if [[ -n "$DOMAIN" ]]; then
    log "Requesting SSL certificate for $DOMAIN..."
    mkdir -p /var/www/certbot
    certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos \
        --email "admin@$DOMAIN" --redirect 2>/dev/null || \
        warn "Certbot failed — run manually: certbot --nginx -d $DOMAIN"
fi

# ── 10. Systemd service ────────────────────────────────────────────
cat > /etc/systemd/system/aia-meetings.service << EOF
[Unit]
Description=AIA-Meetings Service
After=docker.service network-online.target
Requires=docker.service
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=$APP_USER
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
ExecStop=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml down
ExecReload=/usr/bin/docker compose -f docker-compose.yml -f docker-compose.prod.yml restart
TimeoutStartSec=120

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable aia-meetings
log "Systemd service created & enabled"

# ── 11. Fail2ban for Nginx ──────────────────────────────────────────
cat > /etc/fail2ban/jail.d/aia-meetings.conf << 'F2B'
[nginx-req-limit]
enabled = true
filter = nginx-req-limit
logpath = /var/log/nginx/error.log
maxretry = 10
bantime = 600
findtime = 60
F2B

systemctl restart fail2ban 2>/dev/null || true
log "Fail2ban configured"

# ── 12. Logrotate ──────────────────────────────────────────────────
cat > /etc/logrotate.d/aia-meetings << 'LOGROTATE'
/var/log/nginx/access.log /var/log/nginx/error.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    postrotate
        [ -f /var/run/nginx.pid ] && kill -USR1 $(cat /var/run/nginx.pid)
    endscript
}
LOGROTATE
log "Logrotate configured"

# ── 13. Deploy scripts ─────────────────────────────────────────────
chmod +x "$APP_DIR/deploy/scripts/"*.sh 2>/dev/null || true

# ── 14. Build & Start ──────────────────────────────────────────────
log "Building Docker images..."
cd "$APP_DIR"
sudo -u $APP_USER docker compose build --quiet

log "Starting services..."
systemctl start aia-meetings

# Wait for healthy
echo -n "  Waiting for services to be ready"
for i in $(seq 1 30); do
    if docker compose ps --format json 2>/dev/null | grep -q '"Health":"healthy"'; then
        echo
        break
    fi
    echo -n "."
    sleep 2
done
echo

# ── 15. Create initial API key ──────────────────────────────────────
sleep 3
log "Creating initial API key..."
API_KEY=$(curl -sf -X POST "http://localhost:8000/api/v1/auth/keys?name=admin" 2>/dev/null | \
    python3 -c "import sys,json; print(json.load(sys.stdin).get('api_key',''))" 2>/dev/null) || true

# ── Done ────────────────────────────────────────────────────────────
echo
echo "============================================="
echo -e "  ${GREEN}AIA-Meetings deployed!${NC}"
echo "============================================="
echo
echo "  App directory:  $APP_DIR"
echo "  Config file:    $APP_DIR/.env"
[[ -n "$DOMAIN" ]] && echo "  URL:            https://$DOMAIN"
[[ -z "$DOMAIN" ]] && echo "  URL:            http://$(hostname -I | awk '{print $1}'):80"
[[ -n "$API_KEY" ]] && echo "  API Key:        $API_KEY"
echo
echo "  Commands:"
echo "    systemctl status aia-meetings    # Check status"
echo "    systemctl restart aia-meetings   # Restart"
echo "    cd $APP_DIR && make logs         # View logs"
echo "    cd $APP_DIR && make update       # Pull & redeploy"
echo
warn "Don't forget to edit $APP_DIR/.env with your API keys!"
