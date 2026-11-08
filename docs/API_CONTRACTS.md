# HarvestLink AI — API & Integration Contracts

**Status:** Target API contract, version 1.0. Existing endpoints are limited to health and authentication.

## 1. API conventions

- Prefix: `/api/v1`.
- JSON request/response; UTF-8.
- Authentication: bearer token for dashboard/API; webhook signature validation for WhatsApp.
- IDs: UUID for new business records (existing foundation User currently uses integer; migration plan must decide and consistently implement identifiers before marketplace rollout).
- Timestamps: ISO-8601 UTC.
- Quantities/prices: decimal strings in JSON where precision matters, plus explicit unit/currency.
- Errors: stable machine-readable `code`, human-readable `message`, optional field errors and correlation ID.
- Pagination: cursor or bounded page/limit; enforce maximum page size.
- Never expose internal stack traces, secrets, private evidence URLs or unauthorized records.

## 2. Endpoint groups

| Group | Example routes | Purpose |
|---|---|---|
| Auth | POST /auth/register, POST /auth/login, GET /auth/me | Identity |
| Organizations | GET/POST /organizations, POST /organizations/{id}/members | Profiles and memberships |
| Catalogue | GET /crops, GET /units | Canonical references |
| Listings | POST /listings, GET /listings, GET/PATCH /listings/{id}, POST /listings/{id}/submit | Supply |
| Requirements | POST /buyer-requirements, GET /buyer-requirements, PATCH /buyer-requirements/{id} | Demand |
| Matching | POST /matches/search, GET /matches, GET /matches/{id} | Candidate discovery |
| Market | GET /market-observations, POST /market-observations | Sourced observations |
| Services | GET /service-providers, POST /service-requests, GET /service-requests/{id} | Transport/storage |
| Verification | GET /verification-cases, POST /verification-cases/{id}/decision | Human review |
| Workflows | POST /workflows, GET /workflows/{id}, POST /workflows/{id}/resume | Agent runs |
| Approvals | GET /approvals, POST /approvals/{id}/decision | Human gates |
| Transactions | POST /transactions, GET /transactions/{id}, POST /transactions/{id}/milestones | Lifecycle |
| Webhooks | POST /webhooks/whatsapp | Inbound WhatsApp events |

These are planned routes, not claims that they already exist.

## 3. Core listing request (illustrative)

```json
{
  "crop_code": "MAIZE",
  "variety": "yellow maize",
  "quantity": "5.0",
  "unit": "metric_tonne",
  "quality": {"moisture_percent": "12.0", "grade": "seller_declared"},
  "location": {"country": "NG", "state": "Nasarawa", "lga": "Lafia"},
  "available_from": "2027-01-15",
  "expires_at": "2027-01-31T23:59:59Z",
  "visibility": "marketplace"
}
```

The server validates and stores a draft. It must not infer missing weight, grade or verification status.

## 4. Match result (illustrative)

```json
{
  "match_id": "uuid",
  "listing_id": "uuid",
  "requirement_id": "uuid",
  "status": "candidate",
  "score": 82.5,
  "score_breakdown": {
    "crop_fit": 100,
    "quantity_fit": 90,
    "geography_fit": 75,
    "quality_fit": 80,
    "price_fit": null,
    "trust_fit": 70
  },
  "hard_constraints_passed": true,
  "reasons": ["Crop compatible", "Quantity within buyer range"],
  "warnings": ["Buyer price not supplied"]
}
```

A score never overrides a failed hard constraint or represents a confirmed deal.

## 5. WhatsApp adapter

- Verify provider webhook signature before processing.
- Deduplicate inbound message IDs.
- Map sender identity to an existing account or controlled onboarding flow.
- Keep a conversation state machine; ask one focused question at a time for missing fields.
- Convert messages into the same canonical application commands used by the dashboard.
- Respect template, opt-in and messaging-window rules applicable to the official platform.
- Never accept payment credentials or sensitive identity data in ordinary chat.
- Return a concise status and secure dashboard link when a workflow needs review.

## 6. External integration adapter interface

Every integration exposes typed methods and normalized responses. Include provider name, request ID, source timestamp, retrieval timestamp, status, units/currency, validity and error category. Implement timeouts, bounded retries, circuit breaking where useful and safe fallback. Keep provider-specific payloads out of agent prompts where a normalized contract suffices.

## 7. API versioning and compatibility

Do not rename or change a public field without a migration/deprecation plan. Version agent schemas independently from REST routes. Store schema versions on workflow/task records so old runs remain interpretable.
