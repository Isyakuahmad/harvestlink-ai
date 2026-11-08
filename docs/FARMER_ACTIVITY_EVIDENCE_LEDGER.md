# Farmer Activity & Evidence Ledger

## Purpose
The ledger helps a farmer build a chronological, farmer-controlled record of farm operations and supporting evidence. It can produce a structured activity and season report for a lender, cooperative, grant programme or government support application. It does not certify land ownership, audited accounts, creditworthiness, programme eligibility or funding approval.

## Records
- Farm profile: farm name, location, area, area unit and land-access arrangement.
- Season: crop, season label, planted area, planting date and expected harvest date.
- Activity: land preparation, planting, input purchase, fertilising, pest control, irrigation, labour, observation, harvest, sale, delivery or other.
- Amounts: optional quantity, quantity unit, amount and currency. Financial totals must be interpreted by currency and only reflect entered records.
- Evidence: HTTPS reference to a receipt, invoice, photo, delivery note, buyer confirmation or other supporting item.

## Evidence levels
1. `self_reported`: farmer-entered activity with no attachment.
2. `document_supported`: a supporting document or photo is attached. This does not establish authenticity.
3. `independently_verified`: an authorised HarvestLink administrator records a verification decision and reason.

The platform must never silently upgrade a record's evidence level. A document attachment alone is not independent verification.

## Farmer consent and access
- Reports are private to the farmer by default.
- The farmer can create a time-limited share token for a named recipient and stated purpose, scoped to one season or all seasons.
- The farmer can revoke a share at any time. Expired and revoked tokens stop working.
- Share tokens are high-entropy secrets; only their hashes are stored.
- Each shared report access is recorded. The farmer can inspect grants and revoke them.
- A recipient should receive only the report scope the farmer explicitly selected.

## API
- `POST /api/v1/farm-records/farms` and `GET /api/v1/farm-records/farms`
- `POST /api/v1/farm-records/seasons` and `GET /api/v1/farm-records/seasons`
- `POST /api/v1/farm-records/seasons/{season_id}/activities`
- `GET /api/v1/farm-records/seasons/{season_id}/activities`
- `POST /api/v1/farm-records/activities/{activity_id}/evidence`
- `GET /api/v1/farm-records/report?season_id={id}`
- `POST /api/v1/farm-records/sharing`, `GET /api/v1/farm-records/sharing`, `DELETE /api/v1/farm-records/sharing/{id}`
- `GET /api/v1/farm-records/shared/{access_token}` (limited public, token-authorised report)
- `POST /api/v1/farm-records/admin/evidence/{id}/verify` (administrator only)

## Current MVP limitations
- Evidence is referenced by HTTPS URI; binary uploads, malware scanning, OCR and WhatsApp media ingestion are future work.
- Report output is structured JSON; branded PDF/CSV generation is a follow-up.
- Natural-language and voice extraction are not enabled yet. WhatsApp messages must not be treated as saved records until the farmer confirms extracted fields.
- Financial summaries are indicative records, not audited financial statements.
- This feature supports documentation for applications; it does not submit applications or promise a loan/grant decision.
