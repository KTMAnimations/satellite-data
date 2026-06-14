#!/usr/bin/env bash
#
# Self-contained backend setup for geotiles.tech (Ubuntu + nginx).
# Run as the server owner on the VM that serves geotiles.tech.
#
# PREREQUISITE — drop the NEW Earth Engine key JSON here first:
#     /opt/satellite-data/backend/credentials/gee-service-account.json
#   (Get it from the project owner. It is NOT in git.)
#
# Then:   sudo bash setup-backend.sh
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/satellite-data}"
REPO_URL="${REPO_URL:-https://github.com/KTMAnimations/satellite-data.git}"
RUN_USER="${RUN_USER:-ubuntu}"
KEY_PATH="$APP_DIR/backend/credentials/gee-service-account.json"
OLD_KEY_ID="3fca7454a34d65a6206da3ea27fb52adf9d2b1c0"

echo ">> [1/7] System packages ..."
apt-get update -y
apt-get install -y python3-venv python3-pip git curl

echo ">> [2/7] Code into $APP_DIR ..."
if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" pull --ff-only || echo "   (pull skipped; using existing checkout)"
else
  mkdir -p "$(dirname "$APP_DIR")"
  git clone "$REPO_URL" "$APP_DIR"
fi

echo ">> [3/7] Verify the Earth Engine key ..."
# Convenience: stage the key anywhere and pass GEE_KEY_SRC=/path/to/key.json
if [ -n "${GEE_KEY_SRC:-}" ] && [ -f "$GEE_KEY_SRC" ]; then
  mkdir -p "$(dirname "$KEY_PATH")"
  cp "$GEE_KEY_SRC" "$KEY_PATH"
  echo "   installed key from $GEE_KEY_SRC"
fi
if [ ! -f "$KEY_PATH" ]; then
  echo "!! Missing $KEY_PATH"
  echo "!! Re-run with the key staged, e.g.:  sudo GEE_KEY_SRC=~/gee-key.json bash setup-backend.sh"
  exit 1
fi
if grep -q "$OLD_KEY_ID" "$KEY_PATH"; then
  echo "!! $KEY_PATH is the OLD Google-DISABLED key. Replace with the NEW key and re-run."; exit 1
fi

echo ">> [4/7] Python venv + deps ..."
python3 -m venv "$APP_DIR/backend/.venv"
"$APP_DIR/backend/.venv/bin/pip" install --upgrade pip
"$APP_DIR/backend/.venv/bin/pip" install -r "$APP_DIR/backend/requirements.txt"

echo ">> [5/7] Production .env (overwrites stale committed .env; backs it up) ..."
if [ -f "$APP_DIR/.env" ] && ! grep -q "ENVIRONMENT=production" "$APP_DIR/.env"; then
  cp "$APP_DIR/.env" "$APP_DIR/.env.bak.$(date +%s)"
fi
# Preserve an existing ADMIN_TOKEN if present, else generate one. It gates the
# in-app admin pages (including the Earth Engine key-upload page).
ADMIN_TOKEN="$(grep -E '^ADMIN_TOKEN=' "$APP_DIR/.env" 2>/dev/null | head -1 | cut -d= -f2-)"
if [ -z "$ADMIN_TOKEN" ]; then
  ADMIN_TOKEN="$(openssl rand -hex 32 2>/dev/null || head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  GENERATED_TOKEN=1
fi
cat > "$APP_DIR/.env" <<ENV
ENVIRONMENT=production
DEBUG=false
GEE_PROJECT_ID=logical-carver-485406-t0
GEE_SERVICE_ACCOUNT_KEY=$KEY_PATH
DATABASE_PATH=data/satellite.sqlite3
EXPORTS_DIR=data/exports
TILE_CACHE_DIR=data/tile_cache
TILE_CACHE_MAX_MB=2000
CORS_ORIGINS=https://geotiles.tech
ADMIN_TOKEN=$ADMIN_TOKEN
ENV

echo ">> [6/7] Data dirs, ownership, systemd service ..."
mkdir -p "$APP_DIR/data/exports" "$APP_DIR/data/tile_cache"
chown -R "$RUN_USER":"$RUN_USER" "$APP_DIR"
cat > /etc/systemd/system/satellite-backend.service <<UNIT
[Unit]
Description=Satellite Data FastAPI backend (geotiles.tech)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$APP_DIR/backend
EnvironmentFile=$APP_DIR/.env
ExecStart=$APP_DIR/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 2
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable --now satellite-backend
sleep 3

echo ">> [7/7] Health check ..."
if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
  echo "   backend healthy on 127.0.0.1:8000"
else
  echo "!! not healthy — journalctl -u satellite-backend -n 60 --no-pager"; exit 1
fi

if [ "${GENERATED_TOKEN:-0}" = "1" ]; then
  echo
  echo "   ADMIN_TOKEN (save this — needed for the in-app admin & key-upload page):"
  echo "     $ADMIN_TOKEN"
fi

cat <<'NEXT'

========================================================================
 BACKEND IS RUNNING. One manual step left: nginx reverse-proxy.
========================================================================
 1) Edit the geotiles.tech HTTPS server block, e.g.:
      sudo nano /etc/nginx/sites-available/geotiles
    Paste this ABOVE the SPA `location / { ... }` block:

      location /api/ {
          proxy_pass http://127.0.0.1:8000;
          proxy_http_version 1.1;
          proxy_set_header Host              $host;
          proxy_set_header X-Real-IP         $remote_addr;
          proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
          proxy_set_header X-Forwarded-Proto $scheme;
          proxy_connect_timeout 15s;
          proxy_send_timeout    120s;
          proxy_read_timeout    120s;
          proxy_buffering       off;
      }

 2) Test + reload:
      sudo nginx -t && sudo systemctl reload nginx

 3) Verify (Earth Engine auth + data):
      curl -s https://geotiles.tech/api/v1/status/gee
      curl -s https://geotiles.tech/api/v1/regions | head -c 300
========================================================================
NEXT
