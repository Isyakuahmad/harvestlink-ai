# Agent design and first implemented workflows

## Workflow 1
Farmer Agent → Trust Agent → Buyer Matching Agent → Orchestrator.

- Farmer Agent validates and normalizes structured crop offers.
- Trust Agent checks completeness and verification state.
- Buyer Matching Agent compares persisted, approved buyer requirements.
- Orchestrator persists workflow runs, tasks, candidates and traceable results.

## Farmer Activity & Evidence Ledger
The ledger is a capability owned by the Farmer Agent, not a separate autonomous agent in the MVP. It records farm profiles, seasons, activities, evidence references and farmer-consented report sharing. Deterministic API services validate ownership, dates, amounts, access scope and permissions. The WhatsApp adapter uses a constrained first-pass parser and always asks for farmer confirmation before saving activity entries. An LLM-backed extractor can later improve natural-language coverage, but extracted fields must still be shown to and confirmed by the farmer.

## Plant Health & IPM support
Plant health reports capture crop, location, symptoms, severity, affected area and photo references. The current symptom grouping is preliminary triage, not a diagnosis. Guidance prioritizes scouting, field observations, integrated pest management and escalation to local extension specialists. No pesticide brand, active ingredient, dosage or spray rate is prescribed by the MVP. Any future chemical recommendation must be grounded in current Nigerian registration, crop/target-specific label directions and safety intervals.

## Climate support
The WhatsApp channel can store a farmer-shared location and retrieve a short forecast through the Open-Meteo adapter. Climate responses are forecast estimates and planning prompts, not field measurements or guarantees. Localized planting calendars, climate-risk models, flood/drought alerts and agronomist-reviewed recommendations are future capabilities.

## Trust integration
- Self-reported activity remains self-reported.
- Attached evidence changes the activity evidence confidence to document-supported; it does not prove authenticity.
- Only an authorised human reviewer can record independent verification, with a reason and audit event.
- WhatsApp inbound messages are signature-verified and deduplicated by provider message ID.
- Only a farmer's verified linked phone can create records.

## Safety boundaries
- No external buyer contact, publication, payment or binding commitment is initiated by these workflows.
- Farmer records are private unless the farmer creates a time-limited share grant.
- Shared reports are scoped to one season or all seasons, carry a stated recipient and purpose, expire, can be revoked, and record access.
- Do not infer land ownership, income, yield, eligibility or creditworthiness from incomplete records.
- Reports support applications; they do not guarantee loan or grant approval.

## Planned specialist agents
Market Intelligence, Logistics, Storage and expanded Trust & Transaction capabilities follow after real pilot data. Agents must use typed inputs/outputs, cite external evidence and timestamps, and escalate consequential actions for human approval.
