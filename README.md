# Waypoint Voice Lab

A realtime Voice AI support and reliability project built around a synthetic
travel-application domain.

## Core idea

Probabilistic language. Deterministic business state. Measured reliability.

## Current capabilities

- Realtime browser voice interaction with LiveKit
- Deepgram streaming STT
- Groq LLM with structured tool calling
- Cartesia streaming TTS
- Application status lookup
- Missing-document lookup
- Confirmed and idempotent travel-date updates
- Human-support handoff requests
- Critical application-ID normalization
- Turn detection and interruption handling

## Architecture

Browser
→ LiveKit Cloud
→ Python Agent
→ STT / LLM / TTS
→ deterministic FastAPI tools
→ SQLite

## Reliability design

- Backend is the source of truth
- Mutations require deterministic validation
- Travel-date changes use prepare → confirm → apply
- Idempotency protects retries
- Tool failures never become claimed successes
- Human handoff is stored as durable application state

## Local development

Backend:

    uv run fastapi dev backend/app/main.py

Voice agent:

    lk agent dev agent/agent.py

Tests:

    uv run python -m pytest -v

## Status

Core transactional voice workflows are implemented.
Grounded knowledge retrieval, systematic evaluation, frontend polish,
and deployment are in progress.