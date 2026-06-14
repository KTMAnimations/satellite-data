# Push-to-deploy via GitHub Actions

`.github/workflows/deploy.yml` deploys on every push to `main`: it builds the
frontend in the Actions runner, rsyncs it to the VM's web root, then pulls the
backend and restarts it over SSH. This lets you deploy from the repo without the
server owner being online.

Until the secrets below are set the workflow **skips** (it won't fail your pushes).

## One-time setup

### 1. Server owner — on the VM (while they're still around)
Do these once as the deploy user (the SSH user Actions will log in as, e.g. `ubuntu`):

```bash
# a) First-time backend install (systemd service + .env + EE key). See setup-backend.sh.
sudo GEE_KEY_SRC=~/gee-key.json bash /opt/satellite-data/deploy/setup-backend.sh
#    ...and add the nginx /api proxy block it prints, then: sudo nginx -t && sudo systemctl reload nginx

# b) Authorize the GitHub Actions deploy key (PUBLIC key — paste the one-liner you were given):
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAA... github-actions-deploy@geotiles" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys

# c) Let the deploy user restart the backend without a password prompt:
echo "$USER ALL=(root) NOPASSWD: /bin/systemctl restart satellite-backend" | sudo tee /etc/sudoers.d/satellite-deploy
sudo chmod 440 /etc/sudoers.d/satellite-deploy

# d) Make the frontend web root writable by the deploy user (so rsync works without sudo).
#    Replace the path with your actual nginx root for geotiles.tech:
sudo chown -R "$USER" /var/www/geotiles   # <-- your web root
```

### 2. You — in the GitHub repo (Settings → Secrets and variables → Actions)
Add these repository secrets:

| Secret | Value |
|--------|-------|
| `DEPLOY_HOST` | `geotiles.tech` (or the VM's IP) |
| `DEPLOY_USER` | the SSH user, e.g. `ubuntu` |
| `DEPLOY_SSH_KEY` | the **private** deploy key (full contents, incl. BEGIN/END lines) |
| `DEPLOY_WEB_ROOT` | the nginx web root from step (d), e.g. `/var/www/geotiles` (omit to deploy backend only) |

## After setup
Push to `main` (or run the workflow manually from the Actions tab). It will build,
ship the frontend, pull the backend, and restart it — then verify `/health`.

## Notes
- The deploy key is dedicated and scoped to this; revoke it any time by removing
  its line from `~/.ssh/authorized_keys` on the VM.
- The backend service must already exist (step 1a). This workflow updates and
  restarts it; it does not do the first-time install.
- Nginx config is not touched by the workflow — it's a one-time manual step.
