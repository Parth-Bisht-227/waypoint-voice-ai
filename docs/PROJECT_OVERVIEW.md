# Waypoint Voice Lab project overview

Snapshot: 2026-08-31.

## Purpose

Waypoint is a full-stack multilingual voice AI travel-support prototype. A
caller can use the React interface to speak with a LiveKit agent, create or
inspect a synthetic travel application, update a future travel date after
confirmation, request human support, and ask grounded questions about Japan
tourist-visa preparation.

The system follows one central boundary:

> The model handles conversation and tool selection. Typed services own
> validation, identifiers, persistent state, and mutation results.

FastAPI and SQLite are authoritative for application data. Transcripts are
presentation data, while LiveKit application messages contain only a canonical
ID that instructs the browser to refetch the latest record.

## Implemented system

The runtime contains three connected layers:

1. A FastAPI and SQLite service for application creation and reads, missing
   documents, idempotent travel-date changes, human-support requests, and
   short-lived LiveKit tokens.
2. A Python LiveKit agent using Deepgram multilingual STT, Gemini with Cerebras
   fallback, Cartesia TTS, eight typed tools, cached lexical retrieval, runtime
   English/Hindi switching, and session reporting.
3. A React and TypeScript browser client with LiveKit session ownership, remote
   audio, live transcripts, microphone mute/unmute, authoritative application
   refetches, and an isolated decorative canvas.

## System at a glance

~~~mermaid
flowchart LR
    Caller((Caller)) <--> Browser[React voice UI]
    Browser <--> LiveKit[LiveKit room]
    LiveKit <--> Agent[Python agent]
    Agent --> STT[Deepgram STT]
    Agent --> LLM[Gemini primary<br/>Cerebras fallback]
    Agent --> TTS[Cartesia TTS]
    Agent --> API[FastAPI]
    Browser -->|authoritative reads| API
    API <--> DB[(SQLite)]
    Agent --> Knowledge[Curated FAQ + visa entries]
    Agent -. application ID only .-> Browser
~~~

## Design boundaries

- FastAPI and SQLite own application facts and durable mutations.
- The agent accesses business state through typed HTTP tools rather than direct
  database writes.
- The browser validates application messages and refetches FastAPI instead of
  treating transcript text as state.
- One compact lexical retriever serves curated support and Japan visa content;
  unsupported questions return no result.
- Gemini is the primary LLM and Cerebras is the fallback before response output
  or a tool call begins.
- Session reports capture local diagnostic evidence for calls, tool activity,
  provider usage, latency, and shutdown behavior.

## Documentation map

| Document | Use it for |
| --- | --- |
| [Root README](../README.md) | Capabilities, quick start, verification snapshot, and scope |
| [Engineering case study](../project.md) | Design decisions, observed failures, tradeoffs, and outcomes |
| [Architecture](./ARCHITECTURE.md) | Components, ownership boundaries, and runtime flows |
| [Contracts](./CONTRACTS.md) | HTTP, LiveKit, language, persistence, knowledge, and configuration contracts |
| [Local development](./LOCAL_DEVELOPMENT.md) | Setup, processes, tests, smoke checks, and troubleshooting |

## Repository map

~~~text
Waypoint-Voice-Project/
├── agent/                 LiveKit agent, tools, prompt, retrieval, resilience
├── backend/               FastAPI service, SQLite initialization, API tests
├── evals/                 Deterministic checks and provider-backed flow evals
├── frontend/              React + TypeScript LiveKit browser client
├── knowledge/             Curated FAQ and Japan visa entries
├── observability/         Session report writer and local reports
├── tests/                 Agent workflow and observability tests
├── docs/                  Public technical documentation
├── pyproject.toml         Direct Python dependencies
└── uv.lock                Locked Python environment
~~~

## Scope

Waypoint is a local synthetic-data prototype. It does not provide airline
inventory, pricing, booking, payment, ticketing, government visa submission,
authentication, or live human transfer. Visa guidance remains limited to the
curated Japan scenario and must be checked against the linked official sources
because requirements can change.

The source demonstrates the application design, but the unauthenticated local
runtime is not suitable for public deployment without additional security,
privacy, retention, and abuse-control measures.
