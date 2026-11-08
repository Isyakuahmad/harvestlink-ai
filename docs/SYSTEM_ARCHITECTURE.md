# System architecture

## Current foundation
Modular FastAPI application, SQLAlchemy persistence, Pydantic validation and JWT bearer authentication. SQLite supports local development; PostgreSQL is intended for deployment.

## Target multi-agent design
An orchestrator delegates bounded tasks to Farmer, Buyer Matching, Market Intelligence, Logistics, Storage, and Trust & Transaction specialist agents. Agents may share an LLM provider but use distinct instructions, tools, schemas and permissions. Deterministic Python services own calculations, validation, persistence and state transitions.

## Planned components
FastAPI API; PostgreSQL and optional pgvector; Redis worker when asynchronous workloads justify it; Next.js dashboard; official WhatsApp Business Platform; Docker and GitHub Actions. Keep LLM provider integration replaceable.

Normalize units and preserve currency, unit, location, source and timestamp for prices. Expire stale listings. Store agreed transaction terms separately from mutable listings. Audit consequential changes.
