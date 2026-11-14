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

## Live refresh (W4-B4)
`.github/workflows/update-data.yml` runs **every 30 min**, on demand (*Actions → update-data → Run workflow*) and right after each `deploy` from `main` (which publishes `web/` without `live/`):
1. `make live`: fresh download of the last 48 h for the `live` episode (`web/data/episodes.json`, Iberian Peninsula) → pipeline → `validate.py`
2. valid → publish the site with `web/data/processed/live/` and keep a copy as "last good" (Actions cache)
3. failed (FIRMS down, missing key, invalid file) → publish the last good copy instead (or nothing) and mark the run red
4. a final `validate.py` runs right before every publication: an invalid file never reaches the site

The live data is **never committed** (a commit made by a workflow would not trigger `deploy.yml`, and it would bloat the history); `web/data/processed/live/` is in `.gitignore`. Locally: `make live`.

**Setup (once):** add the key as a repository secret named `FIRMS_MAP_KEY` (*Settings → Secrets and variables → Actions*, or `gh secret set FIRMS_MAP_KEY`). The workflow only runs from the default branch, so it starts after the next release to `main`. Scheduled workflows are disabled by GitHub after 60 days without repository activity.
