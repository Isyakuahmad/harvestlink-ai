# Agent design and first implemented workflows

## Workflow 1
Farmer Agent → Trust Agent → Buyer Matching Agent → Orchestrator.

- Farmer Agent validates and normalizes structured crop offers.
- Trust Agent checks completeness and verification state.
- Buyer Matching Agent compares persisted, approved buyer requirements.
- Orchestrator persists workflow runs, tasks, candidates and traceable results.

## Farmer Activity & Evidence Ledger
The ledger is a capability owned by the Farmer Agent, not a separate autonomous agent in the MVP. It records farm profiles, seasons, activities, evidence references and farmer-consented report sharing. Deterministic API services validate ownership, dates, amounts, access scope and permissions. The future conversational Farmer Agent may extract candidate fields from WhatsApp text, voice notes and photos, but must ask the farmer to confirm before persistence.

Trust integration:
- Self-reported activity remains self-reported.
- Attached evidence changes the activity evidence confidence to document-supported; it does not prove authenticity.
- Only an authorised human reviewer can record independent verification, with a reason and audit event.

## Safety boundaries
- No external buyer contact, publication, payment or binding commitment is initiated by the workflow.
- Farmer records are private unless the farmer creates a time-limited share grant.
- Shared reports are scoped to one season or all seasons, carry a stated recipient and purpose, expire, can be revoked, and record access.
- Do not infer land ownership, income, yield, eligibility or creditworthiness from incomplete records.
- Reports support applications; they do not guarantee loan or grant approval.

## Planned specialist agents
Market Intelligence, Logistics, Storage and expanded Trust & Transaction capabilities follow after real pilot data. Agents must use typed inputs/outputs, cite external evidence and timestamps, and escalate consequential actions for human approval.
