# Waypoint Voice Lab

Waypoint is a full-stack voice AI travel-support prototype. It combines a
realtime browser call, multilingual speech, LLM tool use, a typed FastAPI
backend, SQLite persistence, and per-session observability in one local
reference implementation.

> The model handles conversation and tool selection. Typed code and the backend
> own validation, identifiers, persistent state, and mutation results.

The application uses synthetic travel-support records. It does not submit
government visa applications, search live airline inventory, take payments, or
issue tickets.

[Engineering case study](./project.md) ·
[Project overview](./docs/PROJECT_OVERVIEW.md) ·
[Architecture](./docs/ARCHITECTURE.md) ·
[Contracts](./docs/CONTRACTS.md) ·
[Local setup](./docs/LOCAL_DEVELOPMENT.md)

## Capabilities

- Run a realtime call through a React browser UI and LiveKit room.
- Mute and unmute the existing published microphone track without reconnecting.
- Transcribe English, Hindi, and code-switched speech with Deepgram Nova-3
  multilingual STT.
- Answer in English or switch Cartesia TTS to Hindi for Hindi/Hinglish replies.
- Route conversation and tools through Gemini, with Cerebras as the configured
  fallback before any response content or tool call has begun.
- Create a synthetic Waypoint application after collecting and confirming a
  destination and future travel date.
- Read an existing application's status and missing-document list.
- Prepare a travel-date change, ask for natural confirmation, and apply an
  idempotent backend update.
- Create a durable human-support request after the caller explicitly asks for
  one.
- Answer curated Japan tourist-visa questions for an Indian passport holder
  residing and applying in India.
- Publish ID-only refresh hints so the browser refetches authoritative FastAPI
  data instead of trusting assistant prose.
- Save local reports containing conversation, tool, provider-usage, latency,
  state-transition, and shutdown evidence.

The supported visa guidance is intentionally narrow and must be rechecked
against the linked Embassy of Japan and VFS sources because requirements can
change.

## System overview

~~~mermaid
flowchart LR
    Caller((Caller)) <--> UI[React + TypeScript UI]
    UI -->|POST /voice/token| API[FastAPI]
    UI <--> LK[LiveKit room]
    LK <--> Agent[LiveKit Python agent]
    Agent --> STT[Deepgram Nova-3 multi]
    Agent --> LLM[Gemini → Cerebras fallback]
    Agent --> TTS[Cartesia Sonic 3.5]
    Agent -->|typed HTTP tools| API
    UI -->|authoritative reads| API
    API <--> DB[(SQLite)]
    Agent --> FAQ[Curated FAQ + Japan visa entries]
    Agent -. canonical ID only .-> UI
    Agent --> Reports[Ignored local session reports]
~~~

The browser never receives database credentials or reusable LiveKit secrets.
The LLM never writes SQLite directly. The transcript and LiveKit data messages
are presentation and notification channels, not sources of business truth.

## Important reliability boundaries

| Concern | Current boundary |
| --- | --- |
| Invented application facts | Status, dates, missing documents, created IDs, and handoff IDs come from typed FastAPI responses |
| Invalid new application | FastAPI rejects blank destinations and non-future dates; SQLite allocates the next <code>APP###</code> ID transactionally |
| Duplicate date update | The agent retains one idempotency key for the pending change and FastAPI stores the mutation result in the same transaction |
| Premature mutation | Date changes use separate prepare and apply tools and the voice instructions require confirmation; this conversational sequencing is LLM-governed, while future-date and idempotency rules are deterministic |
| Accidental handoff | The prompt exposes only <code>user_request</code> to the agent and requires an explicit request; FastAPI validates the record and creates the canonical handoff ID |
| Untrusted UI updates | The agent sends only a validated application ID; React refetches FastAPI before updating the card |
| Unsupported knowledge | One cached lexical retriever returns a compact curated answer or a no-result response |
| Provider outage | LiveKit tries Gemini first and Cerebras second, with no retry after streamed content or a tool call begins |
| Queued filler speech | Generic latency fillers were removed after reports showed they could play behind completed answers |
| Hidden call failures | Session reports preserve the event and usage evidence needed to diagnose routing, interruption, latency, and shutdown behavior |

## Technology

| Layer | Stack |
| --- | --- |
| Realtime transport | LiveKit Cloud, <code>livekit-agents</code> 1.7.0 |
| Speech recognition | Deepgram Nova-3, <code>language="multi"</code> |
| LLM/tool routing | Gemini <code>gemini-3.5-flash-lite</code>, Cerebras <code>gpt-oss-120b</code> fallback |
| Speech synthesis | Cartesia Sonic 3.5, Parker voice, runtime English/Hindi language switching |
| Agent workflow | Python 3.11, eight typed tools, per-session state |
| API and persistence | FastAPI, Pydantic, <code>aiosqlite</code>, SQLite |
| Frontend | React 19, TypeScript, Vite, LiveKit Client |
| Verification | pytest, provider-backed agent-flow evals, Vitest, TypeScript build |

## Local quick start

Prerequisites: Python 3.11, [uv](https://docs.astral.sh/uv/), Node.js,
the LiveKit CLI, a LiveKit project, and provider credentials for Deepgram,
Google Gemini, Cerebras, and Cartesia.

~~~powershell
git clone https://github.com/Parth-Bisht-227/waypoint-voice-ai.git
Set-Location waypoint-voice-ai
uv sync --locked
npm ci --prefix frontend
lk cloud auth
Copy-Item agent/.env.example agent/.env.local
~~~

The <code>lk cloud auth</code> step links the LiveKit CLI to a Cloud project and
is needed only once per local CLI setup. Fill <code>agent/.env.local</code>
locally with that project's server credentials and the speech/LLM provider
keys. Never commit it or expose its values through a <code>VITE_...</code>
variable.

Start three terminals from the repository root:

~~~powershell
uv run fastapi dev backend/app/main.py
~~~

~~~powershell
lk agent dev agent/agent.py
~~~

~~~powershell
npm run dev --prefix frontend
~~~

Open the Vite URL, normally <code>http://127.0.0.1:5173</code>. See
[the local-development runbook](./docs/LOCAL_DEVELOPMENT.md) for configuration,
smoke checks, troubleshooting, and database-reset guidance.

## Verification snapshot

Snapshot date: 2026-08-31.

| Suite | Result |
| --- | --- |
| Provider-free Python | 80 passed |
| Provider-backed agent flows | 8 scenarios collect successfully; run deliberately because they consume provider quota |
| Frontend unit tests | 14 passed across 4 files |
| TypeScript check | Passed |
| Vite production build | Passed; 45 modules, approximately 724 kB main JS before optional splitting |
| Live calls | English, Hindi/Hinglish switching, Gemini→Cerebras fallback, grounded visa answers, application creation, microphone controls, interruption, and clean shutdown exercised across focused calls |

Run deterministic and provider-backed checks separately:

~~~powershell
uv run python -m pytest backend/tests tests evals/test_application_ids.py evals/test_retrieval.py -q
uv run python -m pytest evals/test_agent_flows.py -q
npm test --prefix frontend
npm run check --prefix frontend
npm run build --prefix frontend
~~~

The latest successful multilingual validation report contained five normal
<code>generate_reply</code> speech events and no generic
<code>session.say()</code> filler events. It closed normally after participant
disconnect. Live-call measurements are diagnostic samples, not provider
benchmarks.

## Representative workflow

A representative end-to-end call can include:

1. Ask for <code>APP004</code> status in English.
2. Switch to Hinglish and ask for its missing documents.
3. Ask what an Indian traveler should prepare for a Japan tourist visa.
4. Switch back to English.
5. Create a new synthetic application after confirming destination and date.
6. Mute and unmute the microphone, then end the call.

A separate mutation path can prepare a future travel-date change for an
existing application, wait for confirmation, apply it once, and trigger an
authoritative card refetch after FastAPI succeeds.

## Scope and limitations

- All application data is synthetic and the runtime is intended for local use.
- Hindi/Hinglish STT, code-switching, interruption detection, and pronunciation
  remain provider- and microphone-dependent.
- Language switching is explicit at runtime; tool arguments and stored data
  remain canonical English values.
- Visa coverage is limited to short-term Japan tourism for the documented India
  scenario. There is no live web search.
- Confirmation and explicit-handoff intent are prompt/tool-flow behavior, not
  user authentication or a general authorization system.
- There is no airline inventory, pricing, booking, payment, upload, cancellation,
  government submission, or live human transfer.
- The API has no login, per-application authorization, rate limiting, production
  TLS/origin policy, or report-retention policy.
- Session reports may contain transcript content and must be treated as
  sensitive local artifacts.
- The large initial LiveKit frontend bundle and automated browser end-to-end
  testing remain optional engineering follow-ups.

The prototype should not be exposed as a public service without authentication,
authorization, secure deployment, abuse controls, secret management, and a
privacy/retention design.

## Documentation

- [Engineering case study](./project.md)
- [Project overview and documentation map](./docs/PROJECT_OVERVIEW.md)
- [Architecture and trust boundaries](./docs/ARCHITECTURE.md)
- [API, event, persistence, and language contracts](./docs/CONTRACTS.md)
- [Local development and troubleshooting](./docs/LOCAL_DEVELOPMENT.md)

## License

Released under the [MIT License](./LICENSE).
