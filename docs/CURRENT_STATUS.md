# Current status

## Snapshot

| Item | Value |
| --- | --- |
| Audit date | 2026-08-23 |
| Repository reference | This document describes the audited file state; use the latest Git commit or release tag for the exact revision |
| Overall state | Local V1 is functionally complete and manually exercised; Git publication and portfolio packaging remain |

This file is the most time-sensitive document in the set. Update it after each integration slice.

## Executive assessment

The core architecture is implemented on both sides:

- The backend reliably reads and mutates synthetic application state.
- The agent has grounded tools, deterministic mutation confirmation, and observability.
- The frontend is no longer a mocked voice UI; it contains a real LiveKit browser session layer and reads real application data through typed adapters.

FastAPI now exposes `POST /voice/token`, the token explicitly dispatches `waypoint-agent`, and the agent publishes the ID-only refresh messages expected by the frontend. Automated tests cover both trust boundaries. Human-operated calls through the custom browser UI and LiveKit's UI exercised microphone/STT, agent audio and state, transcript presentation, authoritative card refetches, a confirmed travel-date mutation, end-call cleanup, session restart, and report persistence.

The first complete portfolio take has now been captured with both application-state updates and audio. The remaining work is release packaging: commit the staged V1 work, review the recording, upload the approved cut, reconcile its public link, and publish a reviewable repository release. The source repository may be public while development continues; that is separate from deploying the unauthenticated runtime. Production hardening is required only if this synthetic local demo is later exposed as a public service; neither a frontend redesign nor a backend rewrite is needed for the portfolio milestone.

## Capability matrix

| Area | State | What that means now |
| --- | --- | --- |
| Synthetic application database | Implemented | SQLite initializes four seed applications and supporting tables |
| Application status read | Implemented | FastAPI and agent tool both exist; frontend card also reads it |
| Missing-document read | Implemented | FastAPI and agent tool both exist; frontend combines it with the application record |
| Travel-date backend update | Implemented | Future-date validation, transaction, stored response, and idempotency conflict handling exist |
| Deterministic confirmation gate | Implemented | A later natural but explicit user turn is required; vetoes and replacement dates cannot authorize the update endpoint |
| Human-support request | Implemented | FastAPI creates the durable request; the voice agent requires a deterministic explicit user request before POSTing |
| Grounded support knowledge | Implemented | Local curated FAQ retrieval with deterministic lexical scoring |
| Application-ID normalization | Implemented in agent | Spoken variants normalize to the current `APP###` form; unclear input is rejected |
| Agent observability | Implemented | Turn metrics are logged and end-of-session reports are written locally |
| Pixel-art frontend shell | Implemented | Responsive monochrome UI, accessible controls, favicon, and isolated canvas scene |
| Frontend application reads | Implemented | Real FastAPI reads, runtime validation, loading/not-found/error states, and refetch logic |
| Frontend LiveKit lifecycle | Implemented at code level | Mic, token request, connect, publish, subscribe, reconnect, disconnect, and cleanup paths exist |
| Live transcript | Implemented at code level | LiveKit text streams are reconciled into typed user/assistant entries |
| Remote audio and speaking orb | Implemented at code level | Agent audio playback and `0..1` analyser amplitude are wired |
| Secure token endpoint | Implemented | Unique 10-minute room token, microphone-only publish, subscribe access, no data publish, named dispatch, and generic no-store failures |
| Browser-to-agent voice call | Manually exercised | Real custom-UI and LiveKit-UI calls carried human microphone audio through STT and returned agent audio, state, and transcript |
| Structured application signal receiver | Implemented | Frontend validates agent/topic/exact ID-only keys and refetches FastAPI |
| Structured application signal sender | Implemented | Successful reads/preparation emit context; only a confirmed successful PATCH emits updated |
| Full browser integration flow | Manually exercised with remaining visual QA | Mic/STT, transcript UI, agent state/audio, application context/refetch, confirmed mutation/card refresh, end-call cleanup, and restart were exercised; narrow viewport, keyboard-only, reduced-motion, and autoplay fallback remain unverified |
| Authentication and user scoping | Not in V1 | Anyone able to reach the local API can address a synthetic record by ID |
| Deployment configuration | Not implemented | No production reverse proxy, hosting, TLS, or secret-management setup is present |

## What works right now

### Backend on its own

Starting FastAPI creates or reuses `backend/waypoint.db`. The API can:

- return application status, destination, and travel date;
- distinguish an unknown application from a known application with no missing documents;
- update only to a future date;
- return the same recorded result for a retry with the same idempotency key;
- reject an idempotency key reused for a different request;
- store a human-support request with a backend-generated ID.

### Agent on its own

When LiveKit dispatches a job to the registered `waypoint-agent`, the agent builds this session:

- Silero voice-activity detection;
- Deepgram `nova-3` English STT;
- Groq `openai/gpt-oss-20b` with low reasoning effort;
- Cartesia `sonic-3.5` TTS;
- LiveKit turn detection with fixed endpointing bounds;
- preemptive LLM generation disabled to reduce discarded Groq requests under the current quota;
- six typed tools for application, mutation, handoff, and knowledge workflows;
- per-call pending mutation state;
- deterministic voice-native confirmation tracking with negative/correction vetoes;
- a concise prompt that prepares a complete date before asking exactly one confirmation and defaults to one short spoken sentence;
- metric logging and a final session report.

The agent calls FastAPI at `BACKEND_BASE_URL`, which defaults to `http://127.0.0.1:8000`.

### Frontend with FastAPI running

The initial page loads `APP001` by default, requests the application and missing-document resources through Vite's proxy, validates both payloads, and labels the card `Live record`.

The canvas animation is independent of application and voice state. It pauses on hidden tabs, supports a visible pause/play control, and becomes a static scene under reduced-motion preferences.

### Frontend voice path today

The browser requests microphone permission, posts to `/api/voice/token`, joins the unique LiveKit room, publishes only its microphone, and waits for the explicitly dispatched agent. It accepts remote audio, state, transcript, and application events only from an agent participant.

Token or connection failure still stops the microphone, releases partial resources, exits the connecting state, and shows a retryable message. No reusable token or server secret is present in frontend code.

## Verification performed for this snapshot

### Deterministic Python tests

Command:

```powershell
uv run python -m pytest backend/tests tests evals/test_application_ids.py evals/test_retrieval.py -q
```

Result:

```text
145 passed in 10.55s
```

Coverage in that command includes:

- FastAPI application, document, date-update, idempotency, handoff, and isolated token behavior;
- decoded token TTL, least-privilege grants, named dispatch, configuration precedence, and secret-safe failures;
- explicit-confirmation parsing and the apply gate;
- natural explicit-human-request parsing, scoped negation, informational-query rejection, and a zero-side-effect handoff gate;
- exact ID-only application signals, success ordering, and non-fatal delivery failure;
- observer metrics and report writing behavior;
- application-ID normalization;
- deterministic FAQ retrieval and no-result cases.

### Frontend unit tests

Command:

```powershell
cd frontend
npm test
```

Result:

```text
3 test files passed
10 tests passed
```

Coverage includes:

- voice-token response validation;
- strict ID-only application event validation;
- transcript interim/final reconciliation;
- token-timeout cleanup and microphone release;
- transport/agent UI-state precedence;
- application ID, payload, status, and date validation.

### Frontend type-check and production build

Command:

```powershell
cd frontend
npm run build
```

Result:

```text
TypeScript check passed
Vite production build passed
45 modules transformed
```

The primary minified JavaScript bundle was approximately `722.71 kB` (`198.85 kB` gzip). Vite emitted a non-blocking warning for exceeding its `500 kB` chunk threshold. The LiveKit client is the main reason to consider later code splitting.

### Provider-backed agent-flow evals

Seven tests in `evals/test_agent_flows.py` use a real Groq LLM while replacing every production tool with a safe mock. They cover tool routing, multi-turn confirmation behavior, explicit and accidental handoff choice, incomplete-date clarification, and refusal to invent unsupported baggage policy.

Command:

```powershell
uv run python -m pytest evals/test_agent_flows.py -v
```

Latest complete result: `7 passed in 59.95s`. Before that final run, the complete-date case exposed the model asking for a year or confirmation even though the user supplied a month, day, and four-digit year. Improved diagnostics captured the actual assistant text, and targeted prepare-first guidance fixed the latest run without weakening an assertion or adding retries. These checks remain network/provider dependent and may encounter Groq rate limits or routing variance on later runs.

### Real LiveKit Cloud calls

FastAPI, `waypoint-agent`, and Vite were started together against the configured LiveKit project. Human-operated sessions were then run through the custom browser UI, followed by a comparison session in LiveKit's UI. Together, the runs proved:

- short-lived token acceptance, unique-room creation, and named `waypoint-agent` dispatch;
- human microphone audio reaching Deepgram and finalized user transcripts reaching the conversation;
- real agent audio, official listening/thinking/speaking state, and transcript entries reaching the browser;
- application context signals causing authoritative FastAPI-backed card refetches;
- prepare, later deterministic confirmation, one backend PATCH, and the updated date returning to the card;
- End call closing the room and browser media path, followed by a successful new session;
- session shutdown reporting `participant_disconnected` without an agent error and persisting a formatted report.

The final recorded run also showed the guarded date workflow and handoff path in
one session: preparation did not mutate the record, a later confirmation caused
exactly one update, an informational support question did not create a handoff,
and a later explicit human request created exactly one. Its measured assistant
end-to-end latency had a `1.849s` median and `1.959s` maximum across seven
reported turns; the larger perceived cost was spoken-response duration rather
than provider or backend latency. Treat these figures as diagnostic evidence
from one call, not as a benchmark.

One custom-UI run exhibited intermittent gaps during streamed audio, while a later custom-UI run and the LiveKit-UI comparison were acceptable. That points to an intermittent browser/transport/provider streaming issue rather than leaked sessions; it remains a demo risk to monitor, not a claim of benchmark-grade latency.

## Current file-level implementation map

| Path | Responsibility |
| --- | --- |
| `backend/app/main.py` | All current HTTP routes and transaction logic |
| `backend/app/database.py` | SQLite path, schema creation, and seed data |
| `backend/app/schemas.py` | Pydantic request/response contracts |
| `backend/app/voice_tokens.py` | Short-lived LiveKit token policy, configuration, and named dispatch |
| `agent/agent.py` | Agent prompt, tools, confirmation state, providers, server registration |
| `agent/application_signals.py` | Exact ID-only LiveKit application refresh publisher |
| `agent/retriever.py` | Cached deterministic FAQ search |
| `observability/session_observer.py` | Metric logging and report persistence |
| `knowledge/faqs.json` | Grounded support corpus |
| `frontend/src/WaypointScreen.tsx` | Page composition and application/voice integration |
| `frontend/src/api/` | Relative HTTP paths, request errors, application calls, token contract |
| `frontend/src/domain/application.ts` | Runtime validation and application adapter boundary |
| `frontend/src/hooks/useApplication.ts` | Authoritative application resource lifecycle |
| `frontend/src/voice/livekitSession.ts` | Browser LiveKit resource owner and event controller |
| `frontend/src/voice/` | Voice types, state mapping, transcript, audio, and data-message boundaries |
| `frontend/src/components/` | Semantic presentation components and canvas scene |
| `evals/` and `tests/` | Deterministic tests and provider-backed behavioral evals |

## Known limitations and risks

### Immediate verification gaps

- The core desktop voice path has been manually exercised, but it is not covered by an automated browser end-to-end test.
- Narrow viewport, keyboard-only navigation, reduced-motion behavior, and the autoplay recovery control still need a focused manual pass.
- A final clean recording should repeat the portfolio path without streamed-audio gaps or provider-rate-limit retries.

### Security and privacy gaps

- No repository license has been selected for public release.
- The source-only `frontend/ui-inspo/waypoint-frontend-inspo` asset should be removed or have its ownership/provenance confirmed before publication.
- No login, identity, or per-application authorization.
- No rate limiting or abuse controls around the local unauthenticated token endpoint.
- No production origin/CORS policy or reverse-proxy configuration.
- Local session reports may contain conversation content; there is no defined retention, redaction, or access policy.
- The system is designed around synthetic data and should not hold real traveler data in its current form.

### Engineering limitations

- `backend/app/main.py` is compact but contains all routes and SQL directly; a service/repository split will help when scope grows.
- Agent HTTP-tool code repeats request/error patterns.
- Seed travel dates are fixed in 2026 and will eventually fail future-date assumptions in demos.
- The frontend LiveKit dependency currently produces one large initial bundle.
- There is no browser end-to-end test suite.
- Provider-backed evals are network-dependent and can vary with model behavior.
- One custom-UI session produced intermittent streamed-audio gaps; the following custom-UI run and LiveKit-UI comparison were acceptable, so the exact source is not isolated.
- Application IDs are intelligible in the current voice, but deterministic TTS-only formatting would produce more consistently natural "A P P zero zero four" pronunciation than prompt guidance alone. This is V1.1 polish, not a V1 safety blocker.
- The frontend says its transcript is not saved, which is true for browser persistence, but the agent's server-side session report may still contain conversation data. Product copy should make that distinction explicit before release.

## Recommended next milestone

The next milestone is to **publish the completed local V1 as portfolio evidence**:

1. run the deterministic Python suite, frontend tests/check/build, and one deliberately labeled provider-backed eval pass;
2. retain the approved final report as private review evidence and trim or re-record the existing take only if a shorter presentation is preferred;
3. upload the approved demo video outside Git and add its public link to the README;
4. finish the README/case-study presentation with the final video link and selected screenshots;
5. inspect staged files for secrets and generated artifacts, and verify the release has coherent backend, agent/evaluation, and documentation commits;
6. perform the remaining narrow viewport, keyboard-only, reduced-motion, and autoplay checks before labeling the UI fully accepted.

See [the demo guide](./DEMO_GUIDE.md) for recording flow and [the roadmap](./ROADMAP.md) for the remaining release checklist.

## Updating this status file

After a meaningful change:

1. update the date and commit;
2. change only the affected matrix rows;
3. rerun and record the relevant commands;
4. distinguish focused local tests from provider-backed evals;
5. move completed roadmap items here;
6. keep unverified end-to-end claims explicit.
