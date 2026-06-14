# Deployment (geotiles.tech)

The site runs on an Oracle Cloud Ubuntu VM. **You normally never SSH in** — push
to `main` to ship code, use the Admin UI to rotate keys.

## How it's wired (on the VM)

- **nginx** serves the built frontend from `/opt/geotiles/satellite-data/frontend/dist`
  and reverse-proxies `/api/` → `127.0.0.1:8100`.
- **Backend:** `geotiles-backend.service` (systemd) runs
  `uvicorn app.main:app --port 8100`.
  - Config: `/etc/geotiles/backend.env` (env, NOT in git)
  - GEE key: `/var/lib/geotiles/credentials/gee-service-account.json` (NOT in git)
  - Data/DB/tile-cache: `/var/lib/geotiles/` (tile cache capped at 200 MB)
- **Auto-deploy:** `geotiles-deploy.timer` runs `/usr/local/bin/geotiles-deploy`
  every ~5 min. On a new `origin/main` it: `git reset --hard`, `pip install`,
  `npm ci && npm run build`, restarts the backend, reloads nginx.

## Day-to-day

- **Ship code:** push to `main`. It auto-deploys within ~5 minutes. Done.
- **Rotate the Earth Engine key:** open `https://geotiles.tech/admin` → **Credentials**,
  enter the `ADMIN_TOKEN`, paste the new service-account JSON, Update. The key is
  stored server-side at `/var/lib/geotiles/credentials/` and never returned to the
  browser. No SSH, no redeploy needed.
- **Change backend config** (`/etc/geotiles/backend.env`) or **force a deploy:**
  these still need SSH (rare):
  ```bash
  sudo nano /etc/geotiles/backend.env && sudo systemctl restart geotiles-backend
  sudo /usr/local/bin/geotiles-deploy --force      # force a rebuild
  ```

## Notes
- Secrets (`/etc/geotiles/backend.env`, the GEE key, `/var/lib/geotiles/`) live
  **outside** the repo, so `git reset --hard` during deploys never touches them.
- Keep `ADMIN_TOKEN` strong — it gates the in-browser key-rotation page.
