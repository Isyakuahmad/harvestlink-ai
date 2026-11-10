# HarvestLink AI — Data Model

**Status:** Target logical model, version 1.0. The current repository only implements the initial User model. This document defines the intended schema before migrations are written.

## 1. Data ownership and tenancy

All business data belongs to an organization. A farmer may be an individual organization; cooperatives, buyers and service providers may have multiple members. Every tenant-owned table carries `organization_id` directly or through a parent relation. API and tool queries must enforce tenant scope. Platform-wide catalogue and public market observations are explicitly classified as shared data.

## 2. Core entities

| Entity | Purpose | Important fields |
|---|---|---|
| User | Login identity | email, password_hash, active, timestamps |
| Organization | Farmer, cooperative, buyer, transporter, warehouse or admin organization | name, type, status, location |
| Membership | User's organization role | user_id, organization_id, role, status |
| Location | Reusable geographic location | country, state, LGA, town, coordinates, precision |
| Crop | Canonical crop catalogue | code, common_name, aliases, category |
| ProduceListing | Supply offered | owner_org, crop, variety, quantity, unit, quality, location, availability, status, expiry |
| BuyerRequirement | Demand wanted | buyer_org, crop, quantity range, quality, destination, target price, delivery window, status |
| MatchCandidate | Ranked possible supply-demand pair | listing_id, requirement_id, score, breakdown, status, created_at |
| MarketObservation | Sourced market-price context | crop, location, price, currency, unit, market_type, source, observed_at, retrieved_at |
| ServiceProvider | Transport or storage provider | organization, service_type, service area, verification |
| ServiceOffer | Quote/availability response | provider, route/facility, capacity, price, status, validity, evidence |
| VerificationCase | Human or evidence-based review | subject_type/id, checks, status, reviewer, evidence |
| Transaction | Agreed commercial process | parties, immutable terms snapshot, status, currency, approval state |
| DeliveryMilestone | Fulfilment progress | transaction_id, event, status, actor, occurred_at, evidence |
| ApprovalRequest | Human approval gate | action_type, exact payload/version, requester, approver, expiry, status |
| AuditEvent | Append-only security/business trail | actor, action, resource, before/after refs, correlation_id, timestamp |
| WorkflowRun | Orchestration state | workflow_type, actor, organization, status, version, timestamps |
| AgentTask | Specialist task execution | workflow_run_id, agent, input/output refs, status, attempts |
| ToolCall | Tool invocation record | task_id, tool_name, arguments hash, result ref, status, duration |
| EvidenceAsset | Secure uploaded or external evidence | owner, storage key, media type, checksum, review state |

## 3. Listing and requirement rules

- Store numeric quantity as decimal, never binary floating point.
- Every quantity has an explicit canonical unit and original user-entered value.
- Preserve raw quality description alongside normalized quality attributes.
- Store location as structured hierarchy plus optional coordinates and location precision.
- Listings have draft, pending_review, published, paused, reserved, fulfilled, rejected and expired states.
- Buyer requirements have draft, active, paused, fulfilled, cancelled and expired states.
- Expiry is explicit; stale records must not enter matching.
- Updates create version history for commercially material fields.
- Public search returns only fields approved for the record's visibility.

## 4. Unit and price normalization

Represent units with a controlled catalogue and conversion rules. Never assume that a bag, sack or truck has a universal weight. A conversion must include the declared conversion basis and source or be confirmed by the user.

A market observation must include:
- amount and currency;
- price basis/unit (for example NGN per metric tonne);
- product/grade/quality;
- market and geography;
- market type (farmgate/wholesale/retail/indicative/confirmed offer);
- source and source reference;
- observed and retrieved timestamps;
- confidence/limitations and verification status.

Currency conversion records rate, provider/source and timestamp. Never overwrite original price/currency.

## 5. Transaction integrity

When parties accept terms, create a transaction terms snapshot containing crop, grade, quantity, unit, price, currency, delivery location/window, parties, inspection terms and agreed conditions. Later listing edits must not rewrite that snapshot. State changes occur through explicit domain commands and append audit events. Payment and escrow are out of initial MVP scope unless separately integrated and legally reviewed.

## 6. Indexes and constraints

- Unique normalized user email.
- Unique organization membership per user/organization.
- Index listings by status, crop, location, availability and expiry.
- Index buyer requirements by status, crop, destination and delivery window.
- Unique match pair per active listing/requirement version.
- Index market observations by crop, location and observed_at.
- Foreign keys and check constraints for non-negative quantities, valid statuses and required ownership.
- Use database transactions for state changes and approval execution.
- Consider PostGIS only when proximity/routing queries justify it; initial distance can use a tested geo adapter.

## 7. Privacy and retention

Collect only information needed for marketplace operations. Restrict personal contact and identity evidence. Store uploaded files privately, scan/validate them and issue time-limited access links. Define retention and deletion rules for personal data, evidence and audit records before production launch.
