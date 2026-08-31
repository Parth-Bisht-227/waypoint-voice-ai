# Local development runbook

Snapshot: 2026-08-31.

## 1. Prerequisites

- Python <code>>=3.11,<3.12</code>
- <code>uv</code>
- Node.js and npm suitable for Vite 8
- LiveKit CLI (<code>lk</code>)
- a LiveKit project or local server
- Deepgram, Google Gemini, Cerebras, and Cartesia credentials for live calls

The final documentation pass used <code>uv 0.9.15</code> and Node
<code>v22.22.3</code>. These are verified examples, not strict minimums.

## 2. Install

From the repository root:

~~~powershell
uv sync --locked
npm ci --prefix frontend
~~~

## 3. Configure

For LiveKit Cloud, link the CLI to the project used by the local worker:

~~~powershell
lk cloud auth
lk project list
~~~

If multiple projects are linked, select the intended default with
<code>lk project set-default "&lt;project-name&gt;"</code>. This CLI setup is
machine-local and normally needs to be completed only once.

Copy the safe template:

~~~powershell
Copy-Item agent/.env.example agent/.env.local
~~~

Fill the ignored local file:

~~~dotenv
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=
LIVEKIT_API_SECRET=
DEEPGRAM_API_KEY=
GOOGLE_API_KEY=
CEREBRAS_API_KEY=
CARTESIA_API_KEY=
BACKEND_BASE_URL=http://127.0.0.1:8000
~~~

The agent loads <code>agent/.env.local</code>. The FastAPI token route reads
process environment first and then the same ignored file for the three
<code>LIVEKIT_...</code> values.

Never commit credentials or put them in a <code>VITE_...</code> variable.

Optional frontend file <code>frontend/.env.local</code>:

~~~dotenv
VITE_DEFAULT_APPLICATION_ID=APP001
~~~

## 4. Start the application

Use three terminals from the repository root.

### FastAPI

~~~powershell
uv run fastapi dev backend/app/main.py
~~~

- API: <code>http://127.0.0.1:8000</code>
- Swagger: <code>http://127.0.0.1:8000/docs</code>

Startup creates or reuses <code>backend/waypoint.db</code> and inserts any
missing seeds.

### LiveKit agent

~~~powershell
lk agent dev agent/agent.py
~~~

The worker registers as <code>waypoint-agent</code> and waits for named room
dispatch.

### React frontend

~~~powershell
npm run dev --prefix frontend
~~~

Open <code>http://127.0.0.1:5173</code>. Vite forwards
<code>/api/*</code> to FastAPI and removes the prefix.

## 5. Expected behavior

Before a call:

- the pixel-art page renders;
- the application card reads <code>APP001</code> unless configured otherwise;
- loading, not-found, retry, and unavailable states are supported;
- the transcript is empty and the voice session is disconnected.

After pressing **Talk to Waypoint**:

1. the browser requests microphone permission;
2. FastAPI returns a unique room-scoped 10-minute token;
3. the browser connects and publishes one microphone track;
4. LiveKit dispatches <code>waypoint-agent</code>;
5. the UI receives agent state, transcript, remote audio, and validated
   application-ID hints.

While connected:

- Mute/Unmute toggles the existing track without reconnecting;
- English is the initial spoken language;
- a clear Hindi/Hinglish request causes the agent to switch Cartesia to Hindi
  and continue in natural Hinglish;
- switching back to English updates the same session;
- application hints trigger authoritative FastAPI refetches;
- normal turns do not schedule generic spoken latency fillers.

End Call disconnects the room, stops the microphone, detaches audio/analyser
resources, unregisters listeners, and resets mute state.

## 6. API smoke checks

With FastAPI running:

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/applications/APP001
~~~

~~~powershell
Invoke-RestMethod http://127.0.0.1:8000/applications/APP001/missing-documents
~~~

Verify token metadata without printing the signed token:

~~~powershell
$voiceToken = Invoke-RestMethod -Method Post http://127.0.0.1:8000/voice/token
$voiceToken | Select-Object server_url, room_name, participant_identity
~~~

Creating an application changes local SQLite:

~~~powershell
$body = @{
    destination = "Japan"
    travel_date = "2027-04-15"
} | ConvertTo-Json

Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/applications -ContentType "application/json" -Body $body
~~~

Date-update and handoff endpoints are also durable. Prefer Swagger for manual
experiments and use unique idempotency keys for new logical date changes.

## 7. Tests

### Provider-free Python

~~~powershell
uv run python -m pytest backend/tests tests evals/test_application_ids.py evals/test_retrieval.py -q
~~~

Final snapshot: <code>80 passed</code>.

This covers backend validation and persistence, token policy, application
signals, LLM fallback construction/failure handling, pending mutation state,
application and handoff behavior, multilingual switching, lexical retrieval,
and observability without calling an external LLM.

### Provider-backed agent flows

~~~powershell
uv run python -m pytest evals/test_agent_flows.py -q
~~~

Eight scenarios collect successfully. They use the real Gemini→Cerebras chain
but replace production tools with safe mocks. Run deliberately because they
need network access, valid provider keys, quota, and may vary with model
behavior.

### Entire Python suite

~~~powershell
uv run python -m pytest -q
~~~

This includes provider-backed evals.

### Frontend

~~~powershell
npm test --prefix frontend
npm run check --prefix frontend
npm run build --prefix frontend
~~~

Final snapshot:

- 4 Vitest files passed;
- 14 tests passed;
- TypeScript passed;
- Vite built 45 modules;
- the main JavaScript bundle was approximately 724 kB (199 kB gzip);
- Vite's large-chunk warning is non-blocking.

## 8. Manual acceptance check

A short acceptance call should cover:

1. connect and hear the greeting;
2. read <code>APP004</code> status;
3. mute and unmute the microphone;
4. switch to Hinglish;
5. ask one Japan visa question;
6. switch back to English;
7. create a new synthetic application or update an existing date;
8. end the call and confirm the microphone is released;
9. inspect the newest ignored report for normal disconnect and no terminal
   error.

Use headphones when testing interruption or Hindi over agent speech. Short
code-switched phrases may be misrecognized even when the STT connection is
healthy.

## 9. Manual frontend checks

- desktop and narrow widths;
- keyboard order and visible focus;
- Talk, Mute/Unmute, Enable audio, and End Call controls;
- application loading, ready, not-found, retry, and error states;
- microphone-denied and token-failure cleanup;
- listening, thinking, speaking, reconnecting, and disconnected states;
- remote audio and speaking-orb response;
- interim/final transcript replacement;
- transcript drawer;
- scene pause and reduced-motion static frame;
- clean end-call and successful second call.

## 10. Troubleshooting

| Symptom | Check |
| --- | --- |
| Application card cannot connect | FastAPI must run on <code>127.0.0.1:8000</code> |
| Card is not found | Verify the configured/default ID exists in local SQLite |
| Secure-session request fails | Check the three server-side LiveKit variables and Vite proxy |
| Connected but no agent | Confirm worker registration and dispatch both use <code>waypoint-agent</code> |
| Connected but silent | Use Enable audio and inspect the remote agent track |
| Tool reports unavailable | Verify FastAPI and <code>BACKEND_BASE_URL</code> |
| Gemini fails immediately | Check <code>GOOGLE_API_KEY</code> and the configured model/account access |
| Cerebras fallback returns payment/quota error | Check account access and <code>CEREBRAS_API_KEY</code> |
| Hindi becomes incorrect English text | Confirm <code>language="multi"</code>; use a clear complete phrase and headphones |
| Agent pauses then resumes during overlap | A VAD event had no usable transcript and LiveKit classified a false interruption |
| Seed differs from docs | Existing databases retain mutations because seeds use <code>INSERT OR IGNORE</code> |
| Build warns about chunk size | LiveKit is in the initial bundle; non-blocking for this local demo |

## 11. Local data and reset

Ignored generated artifacts include:

~~~text
backend/waypoint.db
observability/reports/
frontend/dist/
frontend/node_modules/
agent/.env.local
~~~

To reset synthetic application data, stop FastAPI, verify the exact database
path, and move the file to a recoverable backup name before restarting:

~~~powershell
Resolve-Path -LiteralPath .\backend\waypoint.db
Move-Item -LiteralPath .\backend\waypoint.db -Destination .\backend\waypoint.backup.db
~~~

Do not perform this reset against real or unverified data.

Session reports can contain transcripts and provider usage. Keep them local and
inspect them before sharing.
