# Docker Setup Guide

## Quick Start

```bash
# Clone the repo
git clone <repo>
cd PlaybookChatbot

# Copy the environment template
cp .env.example .env

# Optional: Add Google Docs credentials
# Place your service_account.json in: backend/credentials/service_account.json

# Optional: Add your playbook data
# Place your cm.json in: data/cm.json

# Build and start
docker compose up --build

# Access
# Frontend: http://localhost
# Backend:  http://localhost:8001
# Docs:     http://localhost:8001/docs
```

---

## Prerequisites

- **Docker** (v20+)
- **Docker Compose** (v2+)
- Optional: **Google Service Account JSON** (for Google Docs integration)
- Optional: **cm.json** (for local fallback data)

---

## What Each Developer Needs

### Minimal Setup (no Google Docs)
Just run:
```bash
cp .env.example .env
docker compose up --build
```

The app starts with `DATA_SOURCE=json` (local fallback). If `data/cm.json` is missing, you'll see a warning but the app won't crash.

### With Google Docs
1. Create a Google Service Account in Google Cloud Console
2. Download the JSON key file
3. Place it at: `backend/credentials/service_account.json`
4. Update `.env`:
   ```dotenv
   DATA_SOURCE=google
   GOOGLE_DOC_ID_MAIN=YOUR_DOC_ID
   GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json
   ```
5. Share the Google Doc with the service account email (Viewer access)
6. Run: `docker compose up --build`

---

## Environment Variables

Copy `.env.example` to `.env` and customize:

| Variable | Default | Notes |
|---|---|---|
| `APP_ENV` | `development` | Set to `production` for prod |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `DATA_SOURCE` | `json` | `json` (local) / `google` (Docs) / `both` (fallback) |
| `DATA_PATH` | *(empty)* | Docker auto-sets to `/data`. Leave empty locally. |
| `ENABLE_DEBUG_ENDPOINTS` | `true` | Set to `false` in production |
| `ENABLE_MAINTENANCE_MODE` | `false` | Set to `true` to disable chat |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `credentials/service_account.json` | Path to OAuth2 key |
| `GOOGLE_DOC_ID_MAIN` | *(empty)* | Google Doc ID (optional) |

---

## File Structure for Distribution

```
PlaybookChatbot/
├── .env.example           ← Copy to .env
├── .gitignore
├── docker-compose.yml
├── README.md
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── config.py
│   ├── main.py
│   ├── credentials/         ← developers add service_account.json here
│   ├── logic/
│   └── routes/
├── frontend/
│   ├── Dockerfile
│   ├── vite.config.js
│   ├── nginx.conf
│   ├── package.json
│   └── src/
└── data/
    └── cm.json             ← optional, gitignored
```

---

## What's NOT Committed (and why)

| Path | Reason |
|---|---|
| `.env` | Contains secrets, DB paths, API keys |
| `backend/credentials/` | Contains Google OAuth2 credentials |
| `data/cm.json` | Large playbook data, managed separately |
| `backend/__pycache__/` | Python bytecode |
| `frontend/node_modules/` | Huge folder, rebuilt in Docker |
| `frontend/dist/` | Build artifacts, recreated in Docker |

---

## Common Scenarios

### Scenario 1: Local Development (no Google Docs)
```bash
cp .env.example .env
# Leave DATA_SOURCE=json in .env
docker compose up --build
# Frontend: http://localhost
# Backend: http://localhost:8001
```

### Scenario 2: Using Google Docs
```bash
cp .env.example .env
# Edit .env:
# DATA_SOURCE=google
# GOOGLE_DOC_ID_MAIN=<your-doc-id>
# GOOGLE_SERVICE_ACCOUNT_FILE=credentials/service_account.json

# Place credentials
mkdir -p backend/credentials
# Download from Google Cloud Console and place at:
# backend/credentials/service_account.json

docker compose up --build
```

### Scenario 3: Production Deployment
```bash
cp .env.example .env
# Edit .env for production:
# APP_ENV=production
# LOG_LEVEL=WARNING
# ENABLE_DEBUG_ENDPOINTS=false
# MAINTENANCE_MODE=false

# Set up volumes and credentials securely
# Update docker-compose.yml if needed for your infrastructure

docker compose up --build -d
```

---

## Troubleshooting

### "data/cm.json not found"
**This is expected.** The app gracefully handles it:
- If `DATA_SOURCE=json` only: logs a warning, continues (fails on first chat if no fallback)
- If `DATA_SOURCE=both`: logs a warning, tries Google Docs
- If `DATA_SOURCE=google`: ignores local data, uses Docs only

**Solution:** Either provide `data/cm.json` or use Google Docs integration.

### "Service account file not found"
```
FileNotFoundError: Service account credentials not found: /app/credentials/service_account.json
```

**Solution:**
```bash
# Check that the file exists locally
ls backend/credentials/service_account.json

# If missing, download from Google Cloud Console:
# 1. Go to IAM & Admin → Service Accounts
# 2. Create service account or use existing
# 3. Keys → Add Key → JSON
# 4. Save to backend/credentials/service_account.json
```

### "Cannot connect to backend from frontend"
**Check:** Frontend is trying to reach `http://localhost:8001/api` but:
- Backend not started
- Backend crashed
- Port 8001 already in use

**Solution:**
```bash
# Check running containers
docker compose ps

# View backend logs
docker compose logs backend

# Kill any process on port 8001
lsof -ti :8001 | xargs kill -9

# Rebuild
docker compose up --build
```

### "Port 80 already in use"
**Solution:**
```bash
# Option 1: Free port 80
lsof -ti :80 | xargs kill -9

# Option 2: Use different port in docker-compose.yml
# Change: ports: - "80:80"
# To:     ports: - "3000:80"
# Then access at http://localhost:3000
```

---

## Useful Commands

```bash
# Build everything
docker compose build

# Start everything
docker compose up

# Start in background
docker compose up -d

# View live logs
docker compose logs -f

# View only backend logs
docker compose logs -f backend

# Restart backend
docker compose restart backend

# Stop everything
docker compose down

# Remove volumes too (WARNING: clears data)
docker compose down -v

# Rebuild and restart
docker compose up --build -d

# SSH into backend
docker compose exec backend bash

# Run a command in backend
docker compose exec backend python -m pytest
```

---

## Production Checklist

- [ ] `.env` contains production values
- [ ] `APP_ENV=production`
- [ ] `LOG_LEVEL=WARNING`
- [ ] `ENABLE_DEBUG_ENDPOINTS=false`
- [ ] `MAINTENANCE_MODE=false`
- [ ] `DATA_SOURCE` is set correctly (google/json/both)
- [ ] Google credentials are mounted securely (not in image)
- [ ] `.env` is NOT committed to git
- [ ] `backend/credentials/` is mounted at runtime
- [ ] All secrets are environment variables or volume mounts
- [ ] Health checks are passing
- [ ] Logs are being captured

---

## Architecture

```
┌─────────────────────────────────────┐
│         Developer Machine           │
├─────────────────────────────────────┤
│  .env.example  (committed)          │
│  .env          (local only)         │
│  credentials/  (local, optional)    │
│  data/         (local, optional)    │
└────────────────┬────────────────────┘
                 │
        docker compose up --build
                 │
        ┌────────┴────────┐
        │                 │
  ┌─────▼──────┐    ┌──────▼─────┐
  │  Backend   │    │  Frontend  │
  │ (Python)   │    │ (Node/Vite)│
  │ Port 8001  │    │  Port 80   │
  └─────┬──────┘    └──────┬─────┘
        │                 │
        │ /:8001/api      │
        └────────────────►│
                 (CORS)
```

---

## Support

- Backend logs: `docker compose logs backend`
- Frontend logs: `docker compose logs frontend`
- API docs: http://localhost:8001/docs
- Feature flags: http://localhost:8001/api/flags

