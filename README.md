# HarvestLink AI

**From Harvest to Market, Intelligently.**

A multi-agent platform for coordinating Nigerian agricultural supply chains across farmers/cooperatives and buyers, with a design that can expand to logistics and storage partners.

## Current implementation

### Foundation
- FastAPI backend, JWT authentication and role-aware access.
- SQLAlchemy persistence with Alembic migrations.
- SQLite for local development/tests; PostgreSQL for deployment.
- Ruff and pytest CI.

### Workflow 1 — Farmer → Trust → Buyer Matching → Orchestrator
The first executable workflow is available on the feature/agent-workflow-1 branch.

1. A farmer submits a structured produce offer.
2. Farmer Agent normalizes the offer fields.
3. Trust Agent records checks and marks identity as unverified until independent verification exists.
4. Buyer Matching Agent compares the offer with active, persisted buyer requirements.
5. Orchestrator stores the result and each agent's task trace.

The workflow creates internal match suggestions only. It does not publish listings, contact buyers, or make commercial commitments. Buyer matching uses exact crop normalization, kg/tonne conversion, stated quantity ranges, coarse location overlap and quality-term checks. Price is deliberately not scored until price basis and unit are captured consistently.

### API endpoints

- POST /api/v1/buyer-requirements — authenticated buyer creates a demand requirement.
- GET /api/v1/buyer-requirements — list the signed-in user's requirements.
- POST /api/v1/workflows/produce-offers — authenticated farmer submits an offer and runs the complete workflow.
- GET /api/v1/workflows/{workflow_run_id} — farmer retrieves their own workflow result.

Use the interactive API docs at /docs to try the endpoints. Public farmer registration creates an unverified farmer account and a pending verification case. Buyer registration is available at `POST /api/v1/auth/register/buyer`; it creates a buyer profile and a pending verification case. Buyer demand creation is blocked until an administrator approves the buyer.

### Buyer onboarding and human approval
- `POST /api/v1/auth/register/buyer` — buyer account plus organization/contact profile.
- `GET /api/v1/admin/verification-cases` — administrator review queue.
- `POST /api/v1/admin/verification-cases/{case_id}/decision` — approve or reject with a mandatory reason.
- Farmer identity approval changes the farmer verification state. A produce listing is reviewed separately; it can only be approved after its farmer identity is verified.
- Buyer approval unlocks buyer requirement creation.
- Every decision is recorded in the audit log.
- Rejected users/listings remain blocked.

Configure trusted administrator email addresses using `ADMIN_EMAILS=admin@example.com` before the administrator logs in. The allowlist is server configuration; public registration cannot choose the admin role. For an existing account, set the allowlisted email and sign in again to apply the role. Never expose admin email allowlists in client code.

Listings and buyer contact remain gated; approval records do not themselves send messages, publish data externally, or make commercial commitments.

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

Create a migration after changing SQLAlchemy models:

```bash
alembic revision --autogenerate -m "describe the schema change"
```

Review every generated migration before applying it. Autogenerate is a draft, not a substitute for reviewing data preservation, constraints, indexes, defaults and downgrade behavior.

Inspect migration state:

```bash
alembic current
alembic history
```

Roll back one revision when safe:

```bash
alembic downgrade -1
```

For a fresh database, run migrations before starting the API. The application does not create database tables on startup. Back up production data before applying migrations; test upgrades and rollbacks against a copy first. Keep database credentials in environment variables and never commit them.

## Quality checks

```bash
ruff check .
pytest
```

Never commit credentials. Replace SECRET_KEY before deployment. Public registration never accepts a role field. Admin role is assigned only from the server-side `ADMIN_EMAILS` allowlist.
