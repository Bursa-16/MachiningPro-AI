# MachiningPro AI — Deployment Guide

Public customer-demo deployment reference.
See `docs/DEMO_GUIDE.md` for the demo workflow and known capability limitations.

---

## Architecture

**Single Render Web Service — same-origin topology.**

FastAPI serves both the REST API (`/api/*`) and the React SPA (`frontend/dist/`).
No database, no persistent disk, no CDN required for the demo deployment.

```
Browser → https://machiningpro-ai-demo.onrender.com
            ├─ /api/*         →  FastAPI handlers (auth, catalogs, NC, drawing analysis)
            ├─ /assets/*      →  Vite JS/CSS bundle (StaticFiles)
            ├─ /branding/*    →  Logo assets (StaticFiles)
            ├─ /favicon.svg   →  SPA catch-all (file exists → served directly)
            └─ /app/*         →  SPA catch-all → index.html (React Router handles routing)
```

**Why single service:** `API_BASE = '/api'` in the frontend is a relative path.
Same-origin deployment requires no VITE_API_URL change and no CORS configuration.

---

## Render Service

| Setting | Value |
|---|---|
| Service name | `machiningpro-ai-demo` |
| Service type | Web Service |
| Environment | Python |
| Plan | **Starter** ($7/month — no cold starts) |
| Deploy branch | `main` |
| Health check path | `/api/health` |

> **Free tier warning:** Render's free tier sleeps after 15 minutes of inactivity.
> Cold-start time is ~50 seconds — unacceptable during a live customer demo.
> Use **Starter** or above.

---

## Build & Start Commands

```
Build command:  cd frontend/app && npm ci && npm run build && cd ../.. && pip install .
Start command:  uvicorn backend.api.app:app --host 0.0.0.0 --port $PORT
```

**What the build command does:**
1. `cd frontend/app && npm ci` — installs Node.js dependencies from lockfile (deterministic)
2. `&& npm run build` — Vite production build → `frontend/dist/`
3. `&& cd ../.. && pip install .` — installs Python package from `pyproject.toml`

**Note:** Render's Python build environment includes Node.js.
First deploy takes 10–20 minutes (gmsh wheel ~500 MB). Subsequent deploys use the build cache.

---

## Environment Variables

Set all three secrets in the Render dashboard **before first deploy**.
Never commit real values to the repository.

### Required secrets

| Variable | Description | Constraint |
|---|---|---|
| `MACHININGPRO_DEV_JWT_SECRET` | JWT signing secret | **≥ 32 characters** — auth fails closed if absent or too short |
| `MACHININGPRO_DEV_USERNAME` | Demo login username | Any non-empty string |
| `MACHININGPRO_DEV_PASSWORD` | Demo login password | Any non-empty string |

### Optional variables

| Variable | Default behaviour when absent | Notes |
|---|---|---|
| `CORS_ORIGINS` | CORS middleware not activated | Set only for split-service deployment (not needed for same-origin) |
| `MACHININGPRO_TOOLLIFE968_SOURCE_PATH` | Tool Life Explorer runs from in-catalog data | Windows local paths must NOT be used on Render — leave unset |
| `MACHININGPRO_CUTTING_PARAM_REF_PATH` | Cutting param queries return `NO_MATCH` | Leave unset unless a reference file is deployed |

### Frontend environment variables

None required. `API_BASE = '/api'` is a relative path that resolves to the serving host in same-origin deployment.

---

## Secret Handling

- Secrets are read from environment variables at runtime, never committed to git.
- `MACHININGPRO_DEV_JWT_SECRET` must be ≥ 32 characters. Generate with:
  ```
  python -c "import secrets; print(secrets.token_hex(32))"
  ```
- JWT tokens have a 24-hour expiry and are stored in `sessionStorage` (cleared on tab close).
- The API returns `401` immediately if any required env var is absent.

---

## CORS Configuration

**Same-origin deployment (default):** leave `CORS_ORIGINS` unset. No CORS middleware is activated.

**Split deployment (future):** set `CORS_ORIGINS` to the exact frontend origin:
```
CORS_ORIGINS=https://machiningpro-ai-demo.onrender.com
```
Wildcard (`*`) must never be used — JWT credentials are in play.

---

## Tool Life Deployment Policy

The `MACHININGPRO_TOOLLIFE968_SOURCE_PATH` environment variable points to an optional
Windows-local dataset. This path is **not used in Render deployments**.

On Render, the Tool Life Explorer:
- Operates from in-catalog empirical data (seeded from Python code at import time)
- Does not crash or degrade if the env var is absent
- Displays `Data Not Configured` for fields that depend on the external dataset

Do not set this variable on Render. It is a Windows development-only path.

---

## SPA Routing

React Router handles all `/app/*` routes client-side.
The FastAPI SPA catch-all (`/{full_path:path}`) returns `index.html` for all non-API paths,
enabling browser refresh on any frontend route.

Routes excluded from the catch-all (matched by FastAPI before the catch-all):
- `/api/*` — all API endpoints
- `/docs`, `/openapi.json`, `/redoc` — FastAPI auto-docs (dev only)
- `/assets/*`, `/branding/*` — StaticFiles mounts

---

## Deployment Steps

1. Merge `work/next-stage` → `main` via PR (do not force-push).
2. Connect the repository to Render (New → Web Service → connect repo).
3. Render detects `render.yaml` and pre-fills service configuration.
4. In the Render dashboard, set the three required secret env vars.
5. Trigger first deploy.
6. Wait for build (10–20 min on first deploy).
7. Run the post-deployment smoke test (see below).

---

## Post-Deployment Smoke Test

Run these checks immediately after a successful deploy:

```
1. GET  /api/health
   Expected: 200  {"status":"ok","database_ok":false}

2. POST /api/login  body: {"username":"<demo-user>","password":"<demo-password>"}
   Expected: 200  {"access_token":"<jwt>"}

3. GET  /  (browser)
   Expected: MachiningPro AI React app loads

4. GET  /app/resources/machines  (browser — hard refresh test)
   Expected: React app loads, NOT a 404

5. GET  /app/engineering/cutting-parameters  (browser — hard refresh test)
   Expected: React app loads

6. Navigate: Log in, open all 5 workflow steps from the Dashboard
   Expected: All routes reachable, no broken navigation

7. GET  /api/machines  (with JWT Authorization header)
   Expected: 200  array of machine records

8. Stub routes: /app/planning-quality/turning
   Expected: "Engineering Preview" badge page, not a 404
```

---

## Rollback Guidance

Render retains previous successful deploys.

To roll back:
1. Render dashboard → Service → Deploys
2. Find the last known-good deploy
3. Click "Rollback to this deploy"

For a git-level rollback: revert the offending commit on `main` and push.
Do not use `git reset --hard` or force-push to `main`.

---

## Known Public Demo Limitations

| Limitation | Impact | Notes |
|---|---|---|
| Drawing OCR unavailable | All drawing uploads return `OCR_ENGINE_UNAVAILABLE` | `tesseract-ocr` system package not on Render |
| STEP tessellation slow | First STEP upload may take 10–30 seconds | gmsh initialisation; subsequent uploads faster |
| In-memory state | Uploaded drawings/jobs lost on restart | `MAX_DRAWINGS=20`, `MAX_JOBS=100`; expected for demo |
| Single user | One credential set from env vars | No multi-user or session isolation |
| No rate limiting | API accepts unlimited authenticated requests | Acceptable for controlled demo |
| Render Starter cold start | None (always-on) | Free tier: ~50 s cold start — do not use for demo |
| Cutting param queries | Return `NO_MATCH` without `MACHININGPRO_CUTTING_PARAM_REF_PATH` | Leave unset; module degrades gracefully |

---

## Architecture Decisions

| Decision | Rationale |
|---|---|
| Single service (not split) | `API_BASE='/api'` is relative; no VITE_API_URL or CORS changes needed |
| Starter plan | Eliminates cold starts — required for live customer demo |
| No database | All catalogs are seeded from Python code; no external data dependency |
| No persistent disk | Files processed in-memory; in-memory OrderedDict state is acceptable for demo |
| `npm ci` over `npm install` | Deterministic install from lockfile; reproducible builds |
