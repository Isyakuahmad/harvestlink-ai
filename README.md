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


## WhatsApp Farmer Agent, plant health and climate

The WhatsApp adapter uses Meta's WhatsApp Cloud API webhook. It is opt-in: a farmer signs in to HarvestLink, requests a one-time linking code for their E.164 phone number, then sends `LINK CODE` to the official WhatsApp business number. Only the verified linked number can create farm records.

### Configure Meta WhatsApp Cloud API

Set these environment variables in the deployment secret manager (never commit real values):

- `WHATSAPP_VERIFY_TOKEN`: a long random token used for Meta webhook verification.
- `WHATSAPP_APP_SECRET`: Meta app secret used to validate `X-Hub-Signature-256`.
- `WHATSAPP_ACCESS_TOKEN`: server-side permanent/system-user token with permission to send WhatsApp messages.
- `WHATSAPP_PHONE_NUMBER_ID`: the Meta phone number ID.
- `WHATSAPP_GRAPH_API_VERSION`: supported Graph API version, default `v21.0`.

Configure the Meta webhook callback as `https://YOUR_API_HOST/api/v1/whatsapp/webhook`, subscribe to the `messages` field, and set the verify token to the exact configured value. HTTPS is required. Do not expose access tokens in the dashboard or logs.

### Farmer interaction

Examples:
- `I planted 3 hectares of maize today`
- `I bought 20 bags of fertiliser for ₦850,000`
- `My tomato leaves have yellow spots`
- `WEATHER` or share a WhatsApp location attachment

Activity extraction is deliberately deterministic and limited to supported phrases. The agent creates a pending draft and asks the farmer to reply `YES` before the activity is saved; `NO` cancels it. A matching active crop season must exist. Unsupported messages are not silently written into the ledger.

### Plant health and pesticide safety

Plant health reports are stored as cases for follow-up. Current symptom grouping is preliminary IPM guidance, not an image diagnosis. WhatsApp image media IDs are retained as references; media download, malware scanning and image-model assessment are not enabled in this milestone. Farmers are asked for crop, symptoms, onset and affected area. The service does not prescribe a chemical, brand, concentration or spray rate. Any pesticide use must be based on correct pest identification, current Nigerian registration for the intended crop and target, and the product label; extension review is recommended for severe or spreading problems.

### Climate

`GET /api/v1/climate/forecast?latitude=...&longitude=...` returns a three-day forecast from Open-Meteo for an authenticated farmer. A farmer can share their location through WhatsApp; the coordinates are stored against their linked channel and used when they request WEATHER. Forecasts are estimates and should not be treated as field measurements.

### API routes

- `POST /api/v1/whatsapp/link-challenge` (authenticated farmer)
- `GET /api/v1/whatsapp/webhook` (Meta verification)
- `POST /api/v1/whatsapp/webhook` (signed Meta events)
- `POST /api/v1/plant-health/cases` and `GET /api/v1/plant-health/cases`
- `GET /api/v1/climate/forecast`

Apply migration `alembic upgrade head` before running this release.
