# System architecture

## Current foundation
Modular FastAPI application, SQLAlchemy persistence, Pydantic validation and JWT bearer authentication. SQLite supports local development; PostgreSQL is intended for deployment. Alembic owns schema changes.

## Target multi-agent design
An orchestrator delegates bounded tasks to Farmer, Buyer Matching, Market Intelligence, Logistics, Storage, and Trust & Transaction specialist agents. The Farmer Agent owns the Farm Records & Evidence Ledger capability. Agents may share an LLM provider but use distinct instructions, tools, schemas and permissions. Deterministic Python services own calculations, validation, persistence and state transitions.

## Farmer records data path
Farmer → Farmer Agent → farm profile/season/activity records → evidence references → Trust review → private season report → farmer-controlled, expiring share grant → authorised recipient.

The first release accepts structured API inputs. WhatsApp text, voice and image extraction is a later adapter; extracted fields require farmer confirmation before becoming records. Binary evidence storage and generated PDF/CSV exports are also follow-up work.

## Planned components
FastAPI API; PostgreSQL; optional Redis worker when asynchronous workloads justify it; Next.js dashboard; official WhatsApp Business Platform; Docker and GitHub Actions. Keep LLM provider integration replaceable.

Normalize units and preserve currency, unit, location, source and timestamp for prices. Expire stale listings. Store agreed transaction terms separately from mutable listings. Audit consequential changes and private-report sharing.
