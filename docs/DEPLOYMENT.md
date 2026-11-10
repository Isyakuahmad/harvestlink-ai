# HarvestLink AI — deployment guide

## Current deployment boundary

This is a competition MVP deployment guide, not a claim of production-scale readiness. The current application uses SQLAlchemy and SQLite by default. Deploy one application instance with a persistent writable disk for the SQLite database. Do not run multiple application replicas against the same SQLite file. A PostgreSQL production setup requires adding and validating the appropriate database driver and deployment tests first.

## Required environment

Copy `.env.example` to `.env` and set:

| Variable | Deployment value / guidance |
|---|---|
| `APP_NAME` | `HarvestLink AI` |
| `ENVIRONMENT` | `production` |
| `DEBUG` | `false` |
| `DATABASE_URL` | `sqlite:////data/harvestlink.db` when using the Docker volume below |
| `SECRET_KEY` | Unique random secret of at least 32 characters; never use the example value |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Keep short; default is 30 |
| `ADMIN_EMAILS` | Comma-separated email addresses allowed to register as administrators |
| `WHATSAPP_VERIFY_TOKEN` | Optional; set only when configuring the Meta webhook |
| `WHATSAPP_APP_SECRET` | Optional Meta app secret; store as a secret |
| `WHATSAPP_ACCESS_TOKEN` | Optional Meta access token; store as a secret |
| `WHATSAPP_PHONE_NUMBER_ID` | Optional Meta phone-number ID |

Generate a secret, for example, with `openssl rand -hex 32`. Do not commit `.env`, credentials, access tokens or real participant data. Use HTTPS at the public reverse proxy or hosting platform. Set `DEBUG=false`.

The Meta variables are optional for the web MVP. Live WhatsApp messaging is not enabled until the Meta app, phone number, webhook URL, verification token and signature secret are correctly configured and tested.

## Docker build and run

Build from the repository root:

```bash
docker build -t harvestlink-ai:demo .
```

Create a persistent volume and run database migrations before starting the web process:

```bash
docker volume create harvestlink-data
docker run --rm --env-file .env -v harvestlink-data:/data harvestlink-ai:demo alembic upgrade head
docker run -d --name harvestlink-ai --restart unless-stopped -p 8000:8000 --env-file .env -v harvestlink-data:/data harvestlink-ai:demo
```

The image includes the Alembic configuration and migration directory. The dashboard HTML is packaged with the Python application. The application listens on port 8000.

## Verify the deployment

- `GET /health` should return `{"status":"ok","database":"ok"}`.
- Open `/dashboard` for the role-based web workspace.
- Open `/docs` for the API reference.
- Confirm that the application can write to `/data` and that the volume remains attached after container replacement.

## Administrator bootstrap

Set `ADMIN_EMAILS` before starting the application. Register that address through `POST /api/v1/auth/register` in `/docs`, then sign in to the dashboard and review pending verification cases. Do not use the administrator account for ordinary farmer, buyer or provider activity.

## Database operations

Run `alembic upgrade head` as a release step before deploying a new application version. Back up the SQLite database file on the persistent volume before migrations and on a regular schedule. Test restore procedures. Never delete the volume to resolve an application error.

## Current limitations

- SQLite is the supported default database configuration; this guide assumes a single application instance and persistent storage.
- No payment gateway, escrow, lending or automated settlement is connected.
- Logistics quotes and booking confirmations are records made by the participating provider and parties; no carrier network is integrated or dispatched automatically.
- Delivery notes are participant-submitted and are not independent proof of delivery.
- Meta WhatsApp credentials and production webhook configuration are not supplied by this repository.
- GPS fleet tracking, customs filing, automatic export approvals and multi-country integrations are outside this MVP.
- Use real KYC, privacy notices, consent, data-retention rules, security review and operational support procedures before a public commercial launch.
