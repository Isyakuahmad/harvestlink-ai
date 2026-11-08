# WhatsApp Farmer Agent, plant health and climate integration

## WhatsApp onboarding and security
1. Farmer signs in to HarvestLink and requests a one-time code for their E.164 phone number at `POST /api/v1/whatsapp/link-challenge`.
2. Farmer sends `LINK CODE` to the official WhatsApp business number.
3. Meta webhook signature is checked using the configured app secret; provider message IDs are deduplicated.
4. Only the verified linked number can write farm records. A pending activity draft must be confirmed with YES before it is persisted; NO cancels it.
5. Farmer can inspect or revoke the link using `GET /api/v1/whatsapp/link-status` and `DELETE /api/v1/whatsapp/link`.

The initial deterministic parser supports common activity statements. It is not a general language model and must not guess unsupported quantities or crop seasons. An active crop season must exist before an activity can be recorded.

## Plant health and pesticide support
Plant health cases capture crop, location, symptoms, severity, affected area and optional photo reference. WhatsApp image messages retain the Meta media ID for later retrieval; downloading, malware scanning and computer-vision assessment are future work.

The current symptom grouping is a cautious triage aid, not diagnosis. It prioritizes field observations, integrated pest management and escalation to local extension services. It does not recommend pesticide brands, active ingredients, concentrations or spray rates. If chemical control is considered, advice must be checked against current Nigerian registration and the exact product label for the crop and target pest, including PPE, re-entry and pre-harvest intervals.

## Climate and weather
Farmers can request WEATHER after sharing their WhatsApp location. Coordinates are stored against their linked channel. An authenticated dashboard/API caller can use `GET /api/v1/climate/forecast?latitude=...&longitude=...`.

The current adapter retrieves a three-day Open-Meteo forecast: temperature, precipitation probability/amount and wind. Recommendations are simple planning prompts, not agronomic guarantees. Field-level forecasts, planting calendars, drought/flood alerts and locally calibrated recommendations are future work.

## Deployment checklist
- Set Meta app secret, webhook verify token, access token and phone number ID as deployment secrets.
- Configure Meta webhook callback at `/api/v1/whatsapp/webhook` and subscribe to `messages`.
- Use HTTPS and a currently supported Graph API version.
- Apply Alembic migrations before enabling the webhook.
- Test with a Meta test number before connecting the production WhatsApp number.
- Provide a privacy notice and clear opt-in/opt-out instructions to farmers.
