#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────────────
# Deploy: Background Job Scheduler
# Target: Fresh Ubuntu 24.04 / Debian 12 server
# ──────────────────────────────────────────────

DOMAIN="${1:-your-domain.duckdns.org}"
ADMIN_EMAIL="${2:-admin@example.com}"

echo "==> Deploying Background Job Scheduler"
echo "    Domain:      $DOMAIN"
echo "    Admin Email: $ADMIN_EMAIL"

# ── 1. System packages ────────────────────────
sudo apt-get update
sudo apt-get install -y docker.io docker-compose-v2 nginx certbot python3-certbot-nginx

sudo systemctl enable --now docker

# ── 2. Firewall ───────────────────────────────
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable

# ── 3. Clone / pull project ───────────────────
if [ -d /opt/scheduler ]; then
    cd /opt/scheduler
    git pull
else
    sudo git clone https://github.com/YOUR_USER/background_job_scheduler /opt/scheduler
    cd /opt/scheduler
fi

# ── 4. Environment variables ──────────────────
if [ ! -f .env ]; then
    cat > .env <<EOF
POSTGRES_PASSWORD=$(openssl rand -hex 16)
EMAIL_FAILURE_RATE=0.3
EOF
fi

# ── 5. SSL certificate (Let's Encrypt) ────────
sudo certbot --nginx \
    --non-interactive \
    --agree-tos \
    --email "$ADMIN_EMAIL" \
    --domains "$DOMAIN" \
    || true

# ── 6. Write Nginx config ─────────────────────
sudo tee /etc/nginx/sites-available/scheduler > /dev/null <<NGINX
server {
    listen 80;
    server_name $DOMAIN;
    return 301 https://\$host\$request_uri;
}

server {
    listen 443 ssl http2;
    server_name $DOMAIN;

    ssl_certificate     /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /api/sse/stream {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Connection '';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_buffering off;
        proxy_cache off;
        chunked_transfer_encoding on;
    }

    access_log /var/log/nginx/scheduler_access.log;
    error_log  /var/log/nginx/scheduler_error.log;
}
NGINX

sudo ln -sf /etc/nginx/sites-available/scheduler /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx

# ── 7. Launch containers ──────────────────────
sudo docker compose -f /opt/scheduler/docker-compose.yml up --build -d

echo "==> Deployment complete!"
echo "    API + Dashboard: https://$DOMAIN"
echo "    API docs:        https://$DOMAIN/docs"
echo ""
echo "    Worker runs as a companion container (docker logs -f scheduler_worker_1)."
