# Content Lab — Backend

FastAPI + SQLAlchemy async backend. Python 3.12+.

## Quick start

```bash
# 1. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Configure environment
cp .env.example .env
# Edit .env and fill in your Supabase credentials and OPENROUTER_API_KEY

# 4. Apply DB migrations (Supabase local or remote)
supabase db push                  # or apply supabase/migrations/*.sql manually

# 5. Run the dev server
uvicorn app.main:app --reload --port 8000
```

## Running tests

Unit tests (no DB or AI required):
```bash
pytest tests/unit/ -q
```

Integration tests (requires local Supabase on port 54322):
```bash
pytest tests/ -q
```

Closeout / Sprint 7 invariant tests:
```bash
pytest tests/integration/test_sprint7_closeout.py -v
```

## Running the worker

```bash
python -m app.workers
# or with custom ID:
WORKER_ID=worker-2 python -m app.workers
```

## Accelerated E2E test (from repo root)

Requires VPN **off** and `OPENROUTER_API_KEY` set. Takes ~15–20 minutes.

```bash
# From the repo root (not backend/)
python3 scripts/accelerated_e2e.py 2>&1 | tee /tmp/e2e.log
```

The script starts its own backend and worker, runs a full A→B→C experiment
with 2-minute attribution windows, and writes a report to `reports/`.

## Key environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `DATABASE_URL` | ✓ | — | `postgresql+asyncpg://...` |
| `SUPABASE_JWT_SECRET` | ✓ | — | Must be ≥32 chars |
| `OPENROUTER_API_KEY` | ✓ | — | `sk-or-v1-...` |
| `TIKTOK_METRICS_PROVIDER` | — | `fake` | `fake` or `phone_agent` |
| `ENVIRONMENT` | — | `development` | `development`, `test`, `production` |

See `.env.example` for the full list.
