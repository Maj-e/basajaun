# Operations

## FIRMS API key
- Free key: https://firms.modaps.eosdis.nasa.gov/api/map_key/ (sent by email).
- **Local:** `cp .env.example .env`, then set `FIRMS_MAP_KEY=…`. `.env` is git-ignored — never commit it, never paste the key in chats or issues.
- **GitHub Actions:** stored as the repository secret `FIRMS_MAP_KEY` (set from `.env` with `gh secret set -f .env --repo Maj-e/ulinautas`). Workflows receive it as an environment variable; GitHub masks it in logs.
- **The published site never needs the key**: it only reads static JSON files.
- Recommended: one key for development, a separate one for CI, so a local mistake can't exhaust the key used by the live refresh.

## Quota
- Limit: **5,000 transactions per 10 minutes** per key.
- A full demo download = 4 sources × 3 chunks = **12 requests**. The live refresh (planned) ≈ 4 requests every 30 min.
- Check the remaining quota (does not print the key):
  ```bash
  set -a && . ./.env && set +a
  curl -s "https://firms.modaps.eosdis.nasa.gov/mapserver/mapkey_status/?MAP_KEY=$FIRMS_MAP_KEY"
  ```
- **The demo never calls FIRMS**: it reads committed files, so the quota can't break it.

## Branches and deployment
```
feature/<task-id>-<name> ──PR──► dev ──PR──► main ──► GitHub Pages
```
- PRs target **`dev`**; CI (`make test`) must be green before merging.
- `dev` is merged into **`main`** once checked; every push to `main` runs `.github/workflows/deploy.yml`, which publishes the `web/` folder.
- Published site: **https://maj-e.github.io/ulinautas/** (custom domain later, via `web/CNAME` + DNS).
- A task is done only when it works on the published URL.

## Live refresh (planned, W4-B4)
A scheduled workflow (every 30 min) will run the pipeline for the last 48 h with the secret key, validate the output, and publish the site directly — **without committing** the live data (a commit made by a workflow would not trigger `deploy.yml`, and it would bloat the history). If validation fails, the site keeps the previous version. Scheduled workflows are disabled by GitHub after 60 days without repository activity.
