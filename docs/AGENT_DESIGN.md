# Agent design and first implemented workflow

## Implemented: Workflow 1

The first vertical slice runs as a modular, synchronous workflow:

Farmer Agent → Trust Agent → Buyer Matching Agent → Orchestrator

- **Farmer Agent:** validates and normalizes structured crop, quantity, unit, quality, location, availability and optional asking-price fields.
- **Trust Agent:** records schema checks and verification warnings. No verification is inferred from registration; the current workflow reports identity as unverified.
- **Buyer Matching Agent:** reads active buyer requirements from the database, checks crop and quantity compatibility, compares coarse location labels, and checks quality terms. It does not invent buyers or demand.
- **Orchestrator:** persists the listing, workflow run, per-agent task inputs/outputs and ranked match candidates, then returns a traceable result.

## Safety and current limitations

- Listings remain pending_review; can_publish and can_contact_buyer remain false.
- Match scores are internal heuristic rankings, not guarantees or verified commercial matches.
- Crop aliases and kg/tonne conversions are intentionally small and explicit.
- Location comparison is text overlap only; it is not distance or transport feasibility.
- Price is not scored because price basis (per kg, tonne, lot, etc.) is not yet captured.
- The buyer-requirement API is authenticated, but buyer-role enforcement and buyer account onboarding remain follow-up work.
- The current workflow is synchronous. Durable queueing, bounded retries, timeouts, idempotency keys and human approval records are future hardening work.

## Planned specialist agents

Market Intelligence, Logistics, Storage and expanded Trust & Transaction capabilities follow after the first workflow is tested with real pilot data. Agents must use typed inputs/outputs, cite evidence and timestamps for external facts, and escalate consequential actions for human approval.
