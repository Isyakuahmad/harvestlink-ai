# HarvestLink AI

**From Harvest to Market, Intelligently.**

A multi-agent platform concept for coordinating Nigerian agricultural supply chains across farmers/cooperatives, buyers, transporters and storage providers.

## Milestone 1 — Foundation
Secure FastAPI backend, configuration, SQLAlchemy persistence, registration/login, JWT authentication, tests, Docker and CI. Database schema changes are managed with Alembic migrations. Specialist agents and marketplace workflows are planned, not yet active.

## Local setup
Requires Python 3.11+.

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
alembic upgrade head
uvicorn app.main:app --reload --app-dir backend
```

API docs: http://127.0.0.1:8000/docs

## Database migrations

Apply all pending migrations:

```bash
alembic upgrade head
```

Create a new migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe the schema change"
```

Review every generated migration before applying it. Autogenerate is a draft, not a substitute for reviewing data preservation, constraints, indexes, defaults and downgrade behavior.

Inspect the current migration:

```bash
alembic current
alembic history
```

Roll back one revision when safe:

```bash
alembic downgrade -1
```

For a fresh database, run migrations before starting the API. The application no longer creates database tables on startup. Back up production data before applying migrations; test upgrades and rollbacks against a copy first. Keep database credentials in environment variables and never commit them.

## Quality checks

```bash
pytest
ruff check .
```

Endpoints: `GET /health`, `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`.

SQLite is for local development and tests; PostgreSQL is intended for deployment. Never commit credentials. Replace `SECRET_KEY` before deployment. Public registration always assigns the farmer role; administrator access is granted separately.
