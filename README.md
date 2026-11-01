# HarvestLink AI

**From Harvest to Market, Intelligently.**

A multi-agent platform concept for coordinating Nigerian agricultural supply chains across farmers/cooperatives, buyers, transporters and storage providers.

## Milestone 1 — Foundation
Secure FastAPI backend, configuration, SQLAlchemy persistence, registration/login, JWT authentication, tests, Docker and CI. Specialist agents and marketplace workflows are planned, not yet active.

## Local setup
Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload --app-dir backend
```

API docs: http://127.0.0.1:8000/docs

```bash
pytest
ruff check .
```

Endpoints: `GET /health`, `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`.

SQLite is for local development; PostgreSQL is intended for deployment. Never commit credentials. Replace `SECRET_KEY` before deployment. Public registration always assigns the farmer role; administrator access is granted separately.
