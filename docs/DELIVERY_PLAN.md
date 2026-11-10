# HarvestLink AI — Delivery Plan & MVP Acceptance

**Planning target:** MVP feature-complete by 31 January 2027 (internal target; confirm exact official portal deadline).  
**Principle:** Complete architecture now; implement and harden in vertical slices. Fix issues continuously without losing a working baseline.

## 1. Build order

### Phase A — Foundation hardening
- Alembic migrations and production migration workflow.
- FastAPI lifespan and configuration-driven CORS.
- PostgreSQL integration tests and database constraints.
- Authentication, inactive-user, malformed/expired token and role authorization tests.
- Structured logs, correlation IDs, health/readiness checks.
- Docker and CI reproducibility.

**Exit gate:** fresh database can be created solely through migrations; production startup never silently creates schema; security tests pass.

### Phase B — Marketplace core
- Organizations and memberships with tenant isolation.
- Crop and unit catalogues.
- Farmer produce listing lifecycle.
- Buyer requirement lifecycle.
- Search, filtering, expiry and visibility.
- Seed data for local demo and test fixtures.

**Exit gate:** farmer can publish a valid listing; buyer can publish a requirement; unauthorized organizations cannot read or mutate each other's data.

### Phase C — First agent vertical slice
- Typed agent runtime and orchestrator.
- Farmer Agent extraction and draft preparation.
- Trust Agent completeness checks and review case.
- Matching Agent deterministic candidate search and ranking.
- Workflow persistence, tool traces and failure recovery.

**Exit gate:** one complete supply-to-buyer workflow runs end-to-end with evidence, trace and human review. This is the first competition-quality demo.

### Phase D — Market and fulfilment coordination
- Market Intelligence source adapters and observation records.
- Logistics provider directory and quote requests.
- Storage provider directory and suitability/availability requests.
- Orchestrator assembles comparable options and caveats.

**Exit gate:** demo clearly distinguishes sourced/confirmed data from indicative or unavailable data.

### Phase E — Interfaces
- Dashboard for listings, requirements, matches, workflow history and approvals.
- WhatsApp onboarding and listing creation with one-question-at-a-time collection.
- Shared application services; channels do not duplicate business logic.

**Exit gate:** the same user task can be completed from dashboard and WhatsApp, subject to channel capability.

### Phase F — Pilot and submission readiness
- Interview farmers, cooperatives, buyers, aggregators and service providers.
- Test real listings and buyer requirements with consent.
- Capture correction rates, match relevance, time-to-match and workflow completion.
- Fix usability, security, reliability and data-quality issues.
- Prepare pitch deck, demo video, architecture summary, impact evidence and business model.

**Exit gate:** repeatable live demo, test evidence, clear limitations, user feedback and no critical unresolved security issue.

## 2. Suggested weekly rhythm

- Start each week with one demonstrable user outcome.
- Implement the smallest complete vertical slice.
- Run unit, integration, authorization and workflow tests.
- Review GitHub Actions and inspect failures before proceeding.
- Demo the current branch; log issues and prioritize by severity.
- Keep main protected. Merge only through reviewed pull requests and explicit owner approval.

## 3. MVP scope boundaries

**Must have:** authentication/authorization, organizations, listings, buyer requirements, crop/unit normalization, deterministic matching, agent orchestration, trust review, sourced price context, basic logistics/storage discovery, audit/trace, dashboard, one useful WhatsApp flow, end-to-end tests.

**Can be simplified:** advanced ML ranking, live warehouse integrations, automated route optimization, multilingual voice, sophisticated analytics, native mobile apps.

**Out of MVP:** payment custody/escrow, autonomous contracting, automated disbursement, speculative price prediction, nationwide real-time inventory claims, blockchain, microservices/Kubernetes without demonstrated need.

## 4. Definition of done for every feature

- User problem and acceptance criteria written.
- Authorization and tenant scope enforced server-side.
- Input/output schema and validation added.
- Tests include success, invalid input, unauthorized access and failure case.
- Logs/audit added where action is consequential.
- Documentation and example updated.
- CI green on the feature branch.
- Demonstrated on a working environment.
- No credentials or sensitive personal data committed.

## 5. Competition evidence

Track baseline and outcome with explicit methodology:
- Number of farmers/buyers interviewed and tested.
- Valid listings and buyer requirements created.
- Match precision (human-reviewed relevant matches / reviewed matches).
- Time from listing to first relevant buyer opportunity.
- Listings verified and reasons for rejection.
- Quote response rate and confirmed service options.
- Transactions/deliveries completed (never count an uncompleted match as a sale).
- User-reported savings/time saved, labelled as self-reported or estimated where applicable.

Do not invent pilot results. Keep consent and privacy in place.

## 6. Release gates

- **Alpha:** marketplace workflow works with seeded data.
- **MVP:** agents coordinate a full supply-to-buyer workflow with approval and trace.
- **Pilot:** real participants validate core tasks and provide feedback.
- **Submission candidate:** repeatable demo, documented evaluation, pitch deck and video, known limitations and credible impact evidence.
