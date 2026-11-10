# HarvestLink AI — MVP completion scope

## Product promise

Help agricultural buyers source suitable produce from credible suppliers and coordinate the transaction through delivery, with clear evidence and human approval at consequential steps.

The MVP is a Nigeria-first agricultural procurement coordination product. It is not a general-purpose agricultural super-app.

## Primary demonstration journey

1. A farmer creates an account, registers a farm and crop season, records relevant activity/evidence, and submits a produce offer.
2. The platform validates the offer and creates a review case. An administrator verifies the farmer and approves or rejects the listing with a reason.
3. A buyer registers as an organisation, completes verification, and creates a structured procurement requirement.
4. The matching workflow finds eligible offers using crop, quantity, unit, location, availability and quality criteria. It records why a match qualifies or fails.
5. The buyer reviews a match and expresses interest. The farmer can accept, decline or request clarification. No party is committed automatically.
6. After both parties confirm the commercial terms, a transaction record is created with agreed crop, quantity, price, currency, delivery location, target date and status.
7. The parties may request and compare transport quotations from registered logistics providers. A booking only occurs after explicit human approval and provider confirmation.
8. Delivery evidence and the final transaction outcome are recorded. The farmer and buyer can see the transaction history appropriate to their roles.

## MVP capabilities — must have

- Secure registration, login, role-aware access and ownership isolation.
- Farmer and buyer profiles; business buyer types include exporter, wholesaler, retailer/shop owner, processor and aggregator.
- Farm profiles, seasons, activity records and evidence confidence labels.
- Produce offers with quantity/unit, quality, location, availability and price basis/currency where supplied.
- Buyer requirements with matching quantity/unit, quality, destination and required date.
- Human verification and listing approval with reason and audit history.
- Explainable, deterministic supply-demand matching; no invented buyers, stock, prices or provider availability.
- Buyer access to eligible matches and farmer access to their own offer/match status.
- Buyer interest and farmer response workflow.
- Transaction lifecycle with mutually confirmed terms and auditable status changes.
- Basic logistics-provider profiles and quotation requests/responses; booking is gated by explicit approval and provider confirmation.
- Delivery confirmation and issue/dispute flagging.
- A usable web interface for the primary workflow, plus API documentation for testing.
- Automated tests for permissions, ownership, workflow transitions, migrations and failure cases.
- Clear demo seed data that is labelled as sample data, never represented as real market supply.

## Important but not required to finish the first competition MVP

- Live Meta WhatsApp connection (the adapter can remain optional until credentials and an HTTPS webhook are configured).
- LLM-based natural-language extraction; deterministic structured workflows are acceptable for the first reliable demo.
- Live GPS fleet tracking and automated route optimisation.
- Payment processing, escrow, credit scoring or loan approvals.
- International customs filing or automatic export clearance.
- Image-based crop diagnosis and locally calibrated climate-risk models.
- Multi-country deployments and country-specific association integrations.
- Separate microservices, Kubernetes or a Redis queue before workload requires them.

## Guardrails

- Verification labels must reflect the evidence actually checked.
- Never describe a self-reported claim as independently verified.
- Never fabricate prices, demand, supply, transport capacity, quotations or delivery status.
- Do not contact external parties, publish listings, book transport, accept offers, make payments or create binding commitments without the required user approval.
- Store agreed transaction terms separately from mutable listings and requirements.
- Keep private farmer records private; sharing must be explicit, scoped, expiring and revocable.
- Treat plant-health output as preliminary support, not diagnosis or pesticide prescription.
- Do not promise loans, grants, financing or export approval.

## MVP acceptance gates

The MVP is complete only when all gates below pass:

- [ ] A clean database can be created by running Alembic migrations from zero.
- [ ] A farmer can register, sign in, create a farm/season, and submit a produce offer.
- [ ] An administrator can verify the farmer and approve/reject the listing with an audit record.
- [ ] A buyer can register, be approved, and create a procurement requirement.
- [ ] The matching workflow returns explainable, persisted matches and excludes unverified/ineligible participants.
- [ ] A buyer can review a match and express interest; the farmer can respond.
- [ ] Both parties can confirm transaction terms; unauthorized users cannot view or alter the transaction.
- [ ] A logistics provider can submit a quotation against a request; no booking occurs without approval.
- [ ] Delivery completion or an issue can be recorded with evidence and audit history.
- [ ] A basic web interface supports the demo journey without requiring direct API calls for every step.
- [ ] CI passes linting and all automated tests on the final MVP branch.
- [ ] A repeatable demo script and sample data are available.
- [ ] Deployment instructions, environment variables, migration instructions and known limitations are documented.

## Delivery order

1. Consolidate and verify the existing PR chain and migrations.
2. Complete buyer-facing match discovery and interest/response.
3. Add transaction terms and lifecycle.
4. Add minimal logistics provider and quotation workflow.
5. Build a simple web interface around the same API.
6. Add end-to-end tests, demo seed data and deployment documentation.
7. Run a realistic pilot with at least one farmer and one buyer before making impact claims.

## Explicit scope decision

Do not add more specialist agents for the MVP. Keep the existing agent architecture and implement missing business capabilities as bounded services/workflows. The first proof is one reliable procurement transaction, not the number of agents or features.
