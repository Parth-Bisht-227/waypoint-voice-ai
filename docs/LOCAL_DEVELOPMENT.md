# Local development runbook

## 1. Prerequisites

The project expects:

- Python `>=3.11,<3.12`;
- `uv` for the locked Python environment;
- Node.js and npm suitable for Vite 8;
- the LiveKit CLI (`lk`) for agent development;
- a LiveKit project or local LiveKit server;
- provider credentials for Deepgram, Google Gemini, Cerebras, and Cartesia when running the real agent.

The documentation audit passed with:

```text
uv 0.9.15
Node v22.22.3
```

Those are verified local versions, not strict minimum versions.

## 2. Install dependencies

From the repository root:

```powershell
uv sync --locked
```

Then install the frontend from its lockfile:

```powershell
Set-Location frontend
npm ci
Set-Location ..
```

## 3. Configure local environment

The agent loads an ignored file at `agent/.env.local`. The FastAPI token service reads process environment first and falls back to the same ignored file for the three `LIVEKIT_...` values, so one local server-side file can configure both processes.

Start from the safe tracked template:

```powershell
Copy-Item agent/.env.example agent/.env.local
```

Fill in the copied values locally. Its shape is:

```dotenv
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
DEEPGRAM_API_KEY=
GOOGLE_API_KEY=
CEREBRAS_API_KEY=
CARTESIA_API_KEY=
BACKEND_BASE_URL=http://127.0.0.1:8000
```

Never commit the file or paste its values into frontend code. `LIVEKIT_API_SECRET` and provider keys must never use a `VITE_` prefix because Vite variables are browser-visible.

The optional frontend default can be placed in `frontend/.env.local`:

```dotenv
VITE_DEFAULT_APPLICATION_ID=APP001
```

If omitted, the frontend already defaults to `APP001`.

## 4. Start the local processes

Use separate terminals from the repository root.

### Terminal 1 — FastAPI

```powershell
uv run fastapi dev backend/app/main.py
```

Expected addresses:

- API: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

Startup creates or reuses `backend/waypoint.db` and inserts missing seed records.

### Terminal 2 — LiveKit agent

```powershell
lk agent dev agent/agent.py
```

The command runs with auto-reload and registers the named agent:

```text
waypoint-agent
```

The agent still needs a LiveKit room/job dispatch before it handles a call.

### Terminal 3 — Vite frontend

```powershell
Set-Location frontend
npm run dev
```

Open:

```text
http://127.0.0.1:5173
```

Vite proxies `/api/*` to FastAPI on port `8000` and strips `/api` before forwarding.

## 5. Expected behavior in the current snapshot

With FastAPI, `waypoint-agent`, and Vite running:

- the pixel-art screen renders;
- the application card loads the live `APP001` SQLite-backed record;
- application errors have loading, not-found, retry, and unavailable UI states;
- the transcript starts empty;
- the voice link shows disconnected/ready.

When `Talk to Waypoint` is pressed:

1. the browser asks for microphone permission;
2. the frontend posts to `/api/voice/token`;
3. Vite forwards the request to `/voice/token` on FastAPI;
4. FastAPI returns a unique 10-minute, room-scoped token with explicit `waypoint-agent` dispatch;
5. the browser joins, publishes only its microphone, and receives agent state, audio, transcript, and validated application hints;
6. application hints trigger an authoritative FastAPI refetch rather than carrying business fields.

If configuration or connection fails, the UI shows a retryable error and releases the microphone/partial LiveKit resources.

## 6. API smoke checks

With FastAPI running, these PowerShell commands should return JSON:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/applications/APP001
```

```powershell
Invoke-RestMethod http://127.0.0.1:8000/applications/APP001/missing-documents
```

To verify token issuance without printing the signed credential:

```powershell
$voiceToken = Invoke-RestMethod -Method Post http://127.0.0.1:8000/voice/token
$voiceToken | Select-Object server_url, room_name, participant_identity
```

You can also use the interactive Swagger page at `http://127.0.0.1:8000/docs` for the mutation and handoff endpoints.

Be careful when manually calling the travel-date endpoint: it changes the persistent local SQLite record. Use an intentionally unique idempotency key for each new logical change, and reuse that same key only when retrying the identical request.

## 7. Test commands

### Deterministic Python suite

This command avoids the provider-backed LLM evals:

```powershell
uv run python -m pytest backend/tests tests evals/test_application_ids.py evals/test_retrieval.py -q
```

Result after the simplified provider migration: `79 passed`.

### Provider-backed agent-flow evals

These use the same fixed Gemini-to-Cerebras chain as the production agent, but all production tools are replaced with safe mocks:

```powershell
uv run python -m pytest evals/test_agent_flows.py -q
```

They require both provider API keys, network access, and may take longer or vary with provider behavior.

Eight provider-backed scenarios collect successfully without making network requests. A live browser call has also exercised Gemini primary turns, Cerebras fallback turns, and Gemini recovery in one session. The evals use dynamic future dates and include tool calls plus assistant text in failure diagnostics; do not rerun repeatedly merely to obtain a green sample.

### Entire Python suite

```powershell
uv run python -m pytest -q
```

This includes both deterministic and provider-backed tests.

Run the commands separately when conserving provider quota. The deterministic snapshot is fully green; provider-backed routing remains intentionally strict and may vary between providers and runs.

### Frontend unit tests

```powershell
Set-Location frontend
npm test
```

Result at the documented snapshot: `10 passed` across `3` files.

### Frontend type-check only

```powershell
Set-Location frontend
npm run check
```

### Frontend production build

```powershell
Set-Location frontend
npm run build
```

The build currently passes with a non-blocking large-chunk warning caused mainly by the LiveKit client path.

## 8. Manual frontend checks

After a frontend change, verify at least:

- desktop and narrow/mobile widths;
- keyboard tab order and visible focus rings;
- the skip link to the voice dock;
- application loading, ready, not-found, and error states;
- microphone denied and token-failure states;
- talk/end-call button availability across transport states;
- transcript drawer open/closed behavior;
- browser autoplay fallback through `Enable audio`;
- scene pause/play control;
- `prefers-reduced-motion: reduce` with a static scene;
- tab hiding/restoring without a runaway canvas loop.

- successful connection and agent arrival;
- listening, thinking, speaking, reconnecting, and disconnected states;
- remote agent audio playback;
- orb response to remote audio only;
- interim-to-final transcript replacement without duplicates;
- clean microphone release after ending a call.

## 9. Troubleshooting

| Symptom | Likely cause | Check |
| --- | --- | --- |
| Application card says service unreachable | FastAPI is stopped or Vite proxy target is unavailable | Start FastAPI on `127.0.0.1:8000` |
| Card says not found | Configured/default ID has no SQLite record | Check `VITE_DEFAULT_APPLICATION_ID` and `/applications/{id}` |
| Talk button reports secure-session failure | Missing/invalid LiveKit server configuration, proxy failure, or token-mint failure | Confirm the three `LIVEKIT_...` names without printing values; inspect the generic FastAPI status |
| Browser never asks for microphone | Permission was previously blocked or no input device is available | Check browser site permissions and system input device |
| Voice UI remains on connecting after token work | Agent was not dispatched or registered under a different name | Confirm dispatch uses exactly `waypoint-agent` |
| Connected but silent | Browser autoplay is blocked or no remote agent audio track arrived | Use `Enable audio`; inspect LiveKit participant tracks |
| Agent tools report service unavailable | FastAPI is stopped or `BACKEND_BASE_URL` is wrong | Check agent environment and port `8000` |
| Agent provider startup fails | Missing/invalid provider credentials | Check variable names without printing their values |
| Seed record differs from the table in docs | Local SQLite retains earlier mutations | Remember seeds use `INSERT OR IGNORE`; back up and recreate the local DB only if a reset is intended |
| Frontend build warns about chunk size | LiveKit is bundled into the initial JS chunk | Non-blocking for V1; consider lazy loading/code splitting later |

## 10. Local data and reports

Generated local artifacts are ignored by Git:

```text
backend/waypoint.db
observability/reports/
frontend/dist/
frontend/node_modules/
```

The browser does not persist transcript history. The agent's end-of-session report may still contain conversation and usage data. Treat those reports as sensitive even in development, and do not share them without inspection.

## 11. Scope of this runbook

This document covers reproducible local setup, development processes, tests,
and troubleshooting. The project uses synthetic application data and is not
configured for production deployment.

For the public product overview and architecture, see the root
[README](../README.md), [engineering case study](../project.md), and
[architecture document](./ARCHITECTURE.md).
