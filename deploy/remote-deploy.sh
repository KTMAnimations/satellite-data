#!/usr/bin/env bash
#
# Runs ON the geotiles.tech VM, invoked over SSH by the GitHub Actions deploy
# workflow. Pulls the latest backend code, refreshes deps, and restarts the
# service. Assumes setup-backend.sh has already been run once (systemd unit +
# .env + key in place).
#
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/satellite-data}"

cd "$APP_DIR"
echo ">> Pulling latest main ..."
git fetch --quiet origin main
git reset --hard origin/main

echo ">> Refreshing backend dependencies ..."
"$APP_DIR/backend/.venv/bin/pip" install -q -r backend/requirements.txt

echo ">> Restarting backend service ..."
sudo systemctl restart satellite-backend

echo ">> Waiting for health ..."
for _ in $(seq 1 15); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "   backend healthy"
    exit 0
  fi
  sleep 1
done

echo "!! backend did not become healthy after restart" >&2
journalctl -u satellite-backend -n 40 --no-pager 2>/dev/null || true
exit 1
