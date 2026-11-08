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


## WhatsApp, crop health and climate services

The WhatsApp Cloud API adapter verifies Meta webhook signatures, deduplicates provider message IDs and requires farmers to link their phone using a short-lived one-time code. It only stores parsed farm activities after an explicit YES confirmation. Raw inbound message text is not retained in the inbound event table; message IDs/status and media references are retained for processing and deduplication.

Plant health reports are stored as reviewable cases. The initial triage is symptom-keyword grouping plus conservative integrated pest management guidance; it is not an image diagnosis or pesticide prescription. WhatsApp image media IDs are recorded, but secure media download, scanning and image analysis are not yet enabled.

Climate requests use the Open-Meteo forecast endpoint. A farmer may share WhatsApp location coordinates, which are stored against their linked channel. Coordinates are sent to the weather provider only when a forecast is requested. Forecasts are estimates; the current MVP does not provide a locally calibrated planting calendar or flood/drought risk model.
