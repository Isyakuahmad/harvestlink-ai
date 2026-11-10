# HarvestLink AI — Agent Design & Contracts

**Status:** Target design, version 1.0. Agents are planned contracts; they are not yet implemented in the current foundation.

## 1. Agent runtime rules

Agents are bounded reasoning components, not autonomous administrators. Each agent receives a typed task, authorized context and an allowlisted tool set. It returns a typed result with evidence, warnings and status. Domain services—not the LLM—own validation, calculations, persistence and state transitions.

Shared runtime requirements:
- Unique run/task IDs, correlation IDs and traceable parent-child tasks.
- Versioned input and output schemas.
- Explicit tool allowlists and permission checks on every call.
- Timeouts, bounded retries, token/cost limits and cancellation.
- No arbitrary SQL, shell, unrestricted browsing or unapproved network access.
- No invented entities, quotations, stock, prices, availability or verification.
- Prompt injection resistance: user and retrieved content are data, never instructions that can expand permissions.
- Record model/provider, prompt version, tool calls, evidence and final outcome.
- Human escalation for ambiguity, low-quality evidence, conflicts or consequential actions.

## 2. Central Orchestrator Agent

**Purpose:** Coordinate an end-to-end business workflow and make sure specialist tasks run in the right order.

**Inputs:** canonical user intent, authenticated actor, organization scope, workflow type and relevant record IDs.

**Responsibilities:** classify request into an allowlisted workflow; identify required tasks/dependencies; dispatch agents; validate their response envelopes; manage workflow state; handle partial failure; summarize evidence and next steps; create approval requests where necessary.

**Tools:** read workflow context; create/dispatch task; read validated agent results; request human approval; resume/cancel workflow. It cannot directly edit commercial records or execute payment/contract actions.

**Outputs:** workflow status, structured result, evidence references, warnings, recommended next action and approval request ID if applicable.

**Escalation:** conflicting agent outputs, missing required fields, policy violation, unavailable dependency, repeated tool failure or any action outside its permissions.

## 3. Farmer Agent

**Purpose:** Help farmers and cooperatives onboard and create accurate produce listings.

**Inputs:** farmer message/form, locale, organization membership and optional image/document references.

**Responsibilities:** extract crop, variety, quantity, unit, quality attributes, location, harvest/availability date and contact preference; ask focused questions for missing required fields; map crop aliases to canonical catalogue entries; prepare a draft listing.

**Tools:** read crop catalogue; read own profile; validate location and units; create/update draft listing; upload evidence through secure file service.

**Constraints:** cannot certify quality, ownership, quantity or identity based solely on a message or image. Cannot publish a listing as verified without the required review.

**Output:** normalized draft, missing fields, extraction notes and evidence references.

## 4. Buyer Matching Agent

**Purpose:** Identify and rank compatible buyer requirements for an eligible produce listing, and compatible supply for a buyer requirement.

**Inputs:** listing or requirement ID, normalized product/quantity/quality/location/price terms, visibility scope.

**Hard filters:** compatible crop/product; listing/requirement active and unexpired; quantity within permitted tolerance; required quality constraints met or explicitly unknown; geography/serviceable route; buyer/seller access and trust rules.

**Ranking signals:** crop fit 25%, quantity fit 20%, geography 20%, quality fit 15%, price fit 10%, verification/trust 10%. Weights are configurable and must be evaluated with pilot data. Hard incompatibilities cannot be overridden by a high score.

**Tools:** search eligible listings/requirements; normalize units; calculate distance/route only via approved service; read verification status; save match candidate.

**Output:** ranked candidates, score breakdown, hard-filter results, reasons, missing information and source record IDs.

**Constraints:** a match is an opportunity, not a confirmed sale. Do not expose private buyer/farmer contact data before access policy permits it.

## 5. Market Intelligence Agent

**Purpose:** Provide contextual market observations for a crop, location, quality and unit.

**Inputs:** crop, variety/quality, target location, quantity, unit and requested time window.

**Tools:** approved price-source adapters; internal historical observations; deterministic currency/unit conversion; freshness checker.

**Output:** price range or observations, normalized unit/currency, market/location, source name/reference, observed/retrieved timestamps, quality comparability and caveats.

**Constraints:** distinguish farmgate, wholesale, retail, indicative and confirmed offer prices. Never extrapolate unsupported precision. If no reliable current data exists, say so and request a human-provided quote.

## 6. Logistics Agent

**Purpose:** Discover and compare transport options for a proposed movement.

**Inputs:** origin, destination, commodity, quantity/weight/volume, handling requirements and dates.

**Tools:** approved transporter directory; quote request adapter; distance/route adapter; deterministic cost comparison.

**Output:** provider options, quote status (indicative/requested/confirmed), cost currency/unit, route, capacity evidence, validity period and limitations.

**Constraints:** never fabricate vehicle availability, freight costs or delivery dates. Do not book or commit without explicit human approval and provider confirmation.

## 7. Storage Agent

**Purpose:** Discover appropriate storage facilities and compare suitability.

**Inputs:** commodity, quantity, storage conditions, origin/location, duration and date.

**Tools:** approved warehouse directory; capacity/availability inquiry; storage requirement rules; quote request adapter.

**Output:** candidate facilities, suitability criteria, capacity status, storage conditions, fees and quote status, each with source and timestamp.

**Constraints:** listed capacity is not live availability unless confirmed by the facility. No warehouse booking without approval.

## 8. Trust & Transaction Agent

**Purpose:** Manage verification workflow, listing moderation, transaction readiness and safe lifecycle tracking.

**Inputs:** user/organization/listing/match/transaction references, submitted evidence and policy version.

**Responsibilities:** check completeness and consistency; open verification cases; flag anomalies for human review; enforce listing eligibility; prepare immutable transaction snapshots; track approval and delivery milestones; record disputes and audit events.

**Tools:** read verification policy; create review case; set permitted moderation status; create approval request; snapshot transaction terms; record delivery milestone; append audit event.

**Constraints:** it cannot claim identity/quality verification without authorized evidence/reviewer outcome. It cannot execute payment, release funds, bind parties or settle disputes autonomously.

**Output:** status, checks passed/failed, evidence references, outstanding issues, reviewer action and transaction lifecycle state.

## 9. Agent handoff contract

Each agent receives a task envelope:

```json
{
  "task_id": "uuid",
  "workflow_run_id": "uuid",
  "parent_task_id": null,
  "actor_user_id": "uuid",
  "organization_id": "uuid",
  "task_type": "prepare_produce_listing",
  "input_schema_version": "1.0",
  "input": {},
  "allowed_tools": ["crop_catalogue.search", "listing.create_draft"],
  "deadline": "ISO-8601"
}
```

Each response uses the shared envelope defined in SYSTEM_ARCHITECTURE.md. Unknown fields, malformed outputs and unreferenced factual claims are rejected or sent to review.

## 10. First end-to-end workflow: supply-to-buyer

1. Farmer submits a produce offer.
2. Farmer Agent extracts fields and creates a draft.
3. Deterministic validation checks units, required fields and catalogue mapping.
4. Trust Agent evaluates completeness and verification requirements.
5. Human reviewer approves publication when required.
6. Matching Agent finds and ranks eligible buyer requirements.
7. Market Intelligence adds sourced price context.
8. Logistics and Storage agents retrieve options when relevant.
9. Orchestrator returns a comparison and recommended next action.
10. Human selects whether to contact a buyer or request a quote.
11. Trust & Transaction service records approved terms and milestones.

## 11. Evaluation

Measure:
- Field extraction exact/acceptable accuracy.
- Crop alias and unit normalization accuracy.
- Match precision at top 3 and reasons for rejection.
- Freshness and provenance completeness of price/quote outputs.
- Tool selection success and invalid-call rate.
- Failure recovery and workflow completion rate.
- Unauthorized action prevention (must be 100% in tests).
- Human correction rate and user satisfaction.
- Verified matches and completed deliveries in pilot.
