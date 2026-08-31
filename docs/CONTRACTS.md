# Runtime and data contracts

This document records the contracts audited on 2026-08-23. Use the latest Git commit or release tag for the exact revision. It is intentionally more precise than the project overview so integration work can use it as a checklist.

## 1. URL convention

Frontend code uses relative `/api/...` URLs. During Vite development, `frontend/vite.config.ts` proxies them to `http://127.0.0.1:8000` and removes the `/api` prefix.

| Browser request | FastAPI receives |
| --- | --- |
| `/api/applications/APP001` | `/applications/APP001` |
| `/api/applications/APP001/missing-documents` | `/applications/APP001/missing-documents` |
| `/api/voice/token` | `/voice/token` |

This avoids hardcoding localhost URLs in React components. A production deployment must provide the same routing behavior through its web server or gateway.

## 2. Implemented FastAPI endpoints

The backend currently has no authentication or authorization. These endpoints are suitable for the synthetic local V1 only.

### Read an application

```http
GET /applications/{application_id}
```

Successful response:

```json
{
  "application_id": "APP001",
  "destination": "Solara",
  "status": "blocked",
  "travel_date": "2026-09-10"
}
```

- `200`: record found.
- `404`: `{"detail":"Application not found"}`.

### Read missing documents

```http
GET /applications/{application_id}/missing-documents
```

Successful response with missing documents:

```json
{
  "application_id": "APP001",
  "missing_documents": ["bank_statement"]
}
```

A known application with no missing documents returns `200` and an empty list. An unknown application returns `404`; the backend performs a separate existence check so those cases are not confused.

### Update a travel date

```http
PATCH /applications/{application_id}/travel-date
Content-Type: application/json
```

Request:

```json
{
  "new_date": "2026-12-20",
  "idempotency_key": "date-client-generated-unique-key"
}
```

Successful response:

```json
{
  "application_id": "APP001",
  "old_date": "2026-09-10",
  "new_date": "2026-12-20",
  "changed": true
}
```

Rules:

- `new_date` must be later than the backend's current date; today or a past date returns `400`.
- An unknown application returns `404`.
- The first use of an idempotency key stores the logical request and serialized result in the same transaction as the update.
- Repeating the same key, application, operation, and date returns the original result without applying a second update.
- Reusing the key for a different request returns `409`.
- Request-shape and enum validation failures use FastAPI/Pydantic's `422` response.

The public endpoint itself does not enforce conversational confirmation. That gate currently lives in the agent workflow. A future non-agent caller must implement an equivalent authorization rule or call a higher-level operation that does.

### Create a human-support request

```http
POST /applications/{application_id}/handoffs
Content-Type: application/json
```

Request:

```json
{
  "reason_code": "user_request"
}
```

Successful `201` response:

```json
{
  "handoff_id": "HOF-a1b2c3d4e5",
  "application_id": "APP001",
  "reason_code": "user_request",
  "status": "requested"
}
```

The backend, not the LLM, creates the handoff ID. This records a request for human support; it does not mean a live transfer has occurred.

## 3. Domain enums

### Application status

```text
processing
approved
blocked
action_required
```

### Handoff reason

```text
user_request
unsupported_request
repeated_clarification_failure
backend_failure
state_conflict
critical_entity_uncertain
```

The backend keeps this complete reason enum for direct API compatibility.
The V1 voice agent creates a handoff only for `user_request`, and only when
the latest finalized user transcript deterministically asks for a human.
Missing mutation details, corrections, confusion, and clarification attempts
cannot authorize the agent-side POST.

Negation is scoped to the requested handoff action. “This is not working;
connect me to a human” is an explicit request, while “Please do not connect me
to a human” and “I want to know what a support agent does” are not. The agent
does not concatenate separate finalized turns to manufacture authorization;
ambiguous fragments fail closed, while short direct fragments such as “to a
human” are accepted as completed requests.

### Handoff status

The current backend creates handoffs only with:

```text
requested
```

## 4. Secure voice-token contract — implemented

The frontend calls:

```http
POST /api/voice/token
```

After Vite's rewrite, FastAPI must expose:

```http
POST /voice/token
```

Successful response:

```json
{
  "server_url": "wss://example.livekit.cloud",
  "participant_token": "<short-lived signed participant token>",
  "room_name": "waypoint-unique-room",
  "participant_identity": "browser-unique-identity"
}
```

Contract details:

- All four response fields are emitted by the FastAPI response model.
- `server_url` and `participant_token` are the browser connection inputs.
- `server_url` must use `ws:` or `wss:`.
- `room_name` and `participant_identity` are unique diagnostic values.
- The exact token field in the current frontend is `participant_token`, not `token`.
- The browser sends no API key or provider secret.
- The token lifetime is 10 minutes.
- The token is restricted to its generated room and browser identity.
- It grants room join, subscription, and microphone-source publication only; data publication is explicitly disabled.
- Its room configuration dispatches the registered agent name `waypoint-agent`.
- Both success and error responses use `Cache-Control: no-store`.
- There is intentionally no static-token or browser-secret fallback.

The service reads process environment first and falls back to the ignored server-side `agent/.env.local` file for local development. Invalid/missing configuration or token-minting failure returns a generic `503` without exposing credentials, provider detail, or a partial token. The endpoint is intentionally unauthenticated for the synthetic local V1; it requires authentication, authorization, origin checks, and rate limits before public exposure.

## 5. LiveKit browser protocol

The browser client uses `livekit-client` version `2.22.0`.

### Transport and media

- `createLocalAudioTrack()` requests the microphone with echo cancellation, noise suppression, and automatic gain control.
- `Room.connect(serverUrl, participantToken)` joins the room.
- The local track is published with source `Track.Source.Microphone`.
- Remote audio is accepted only from a participant for which LiveKit reports `participant.isAgent`.
- A remote agent track is attached for playback and passed to `createAudioAnalyser()` for normalized orb amplitude.

### Agent state

The official participant attribute is:

```text
lk.agent.state
```

Recognized values are:

```text
connecting
pre-connect-buffering
initializing
idle
listening
thinking
speaking
disconnected
failed
```

Unknown or absent values become the internal `unavailable` state. Transport failure and reconnecting take precedence when deriving the simpler UI state.

### Transcription

The registered text-stream topic is:

```text
lk.transcription
```

The frontend uses these stream attributes:

| Attribute | Purpose |
| --- | --- |
| `lk.transcribed_track_id` | Required marker that the stream is track transcription |
| `lk.segment_id` | Stable ID for replacing interim text with final text |
| `lk.transcription_final` | String `"true"` means the segment is final |

Transcript entries have the presentation-only shape:

```ts
interface VoiceTranscriptEntry {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  final: boolean;
  timestamp: number;
  participantIdentity: string;
}
```

Only the local participant maps to `user`, and only an agent participant maps to `assistant`. Other participants are ignored.

## 6. Structured application refresh messages — implemented

LiveKit data-message topic:

```text
waypoint.application
```

Allowed payloads:

```json
{
  "type": "application_context",
  "application_id": "APP004"
}
```

```json
{
  "type": "application_updated",
  "application_id": "APP001"
}
```

The current frontend accepts a message only when all of these are true:

- it arrived on `waypoint.application`;
- the sender is a LiveKit agent participant;
- the UTF-8 payload is between 1 and 4,096 bytes;
- the JSON object contains exactly `type` and `application_id`—no business fields;
- `type` is one of the two values above;
- `application_id` matches the expected `APP...` form.

After validation, the browser changes the current application ID and refetches FastAPI. The event is a notification, not an authoritative record.

The agent publishes `application_context` only after a successful authoritative status read, missing-document read, or travel-date preparation that verified the application. It publishes `application_updated` only after FastAPI confirms the PATCH. Publication failure is logged and does not replace or reinterpret the already completed tool result.

This payload is intentionally rejected:

```json
{
  "type": "application_updated",
  "application_id": "APP001",
  "travel_date": "2026-12-20"
}
```

Even if the date were correct, the browser must obtain it from `GET /applications/APP001`.

## 7. Frontend application-domain boundary

The UI consumes a camelCase snapshot:

```ts
interface ApplicationSnapshot {
  applicationId: string;
  destination: string;
  status: 'processing' | 'approved' | 'blocked' | 'action_required';
  travelDate: string;
  missingDocuments: readonly string[];
}
```

The adapter validates both HTTP responses before constructing the snapshot:

- IDs must be non-empty and match the frontend's accepted format.
- The application and missing-document responses must refer to the same ID.
- Status must be a known enum member.
- Travel date must be a real `YYYY-MM-DD` calendar date.
- Document codes must be strings.
- The returned ID must match the requested ID.

Malformed data becomes a controlled service error rather than being rendered as trusted state.

## 8. SQLite schema and seed records

The database path is:

```text
backend/waypoint.db
```

It is created at FastAPI startup and ignored by Git.

| Table | Purpose | Important key |
| --- | --- | --- |
| `applications` | Authoritative application record | `application_id` |
| `missing_documents` | Zero or more document codes per application | `(application_id, document_code)` |
| `idempotency_records` | Original result for each logical mutation key | `idempotency_key` |
| `handoff_requests` | Durable human-support requests | `handoff_id` |

Initial synthetic seed data:

| ID | Destination | Status | Travel date | Missing documents |
| --- | --- | --- | --- | --- |
| `APP001` | Solara | blocked | 2026-09-10 | `bank_statement` |
| `APP002` | Solara | processing | 2026-10-05 | none |
| `APP003` | Norvik | action_required | 2026-09-28 | `passport_scan` |
| `APP004` | Norvik | approved | 2026-11-12 | none |

Seeds use `INSERT OR IGNORE`. An existing local database may therefore differ after previous mutations, which is expected.

`missing_documents` and `handoff_requests` have SQLite foreign keys to `applications`. `idempotency_records.application_id` is a logical reference but is not currently declared as a database foreign key.

## 9. Configuration contract

### Agent environment

The local ignored file is `agent/.env.local`. Never commit its values.

| Variable | Used for |
| --- | --- |
| `LIVEKIT_URL` | LiveKit deployment URL |
| `LIVEKIT_API_KEY` | Server/agent LiveKit credential |
| `LIVEKIT_API_SECRET` | Server/agent LiveKit credential |
| `DEEPGRAM_API_KEY` | Streaming speech-to-text provider |
| `GOOGLE_API_KEY` | Gemini LLM provider and provider-backed evals |
| `CEREBRAS_API_KEY` | Cerebras fallback provider and provider-backed evals |
| `CARTESIA_API_KEY` | Text-to-speech provider |
| `BACKEND_BASE_URL` | Agent-to-FastAPI base URL; defaults to `http://127.0.0.1:8000` |

The provider plugins read their conventional credential variables. `BACKEND_BASE_URL` is read explicitly in `agent/agent.py`. The token service reads the three `LIVEKIT_...` values from the FastAPI process environment first and uses the ignored `agent/.env.local` only as a local-development fallback.

An environment name `CARTESIA_VOICE_ID` may exist locally, but the current agent code does not read it; the voice ID is currently specified in code. Treat that variable as inactive until the implementation is changed.

### Frontend environment

| Variable | Behavior |
| --- | --- |
| `VITE_DEFAULT_APPLICATION_ID` | Initial application card ID; defaults to `APP001` |

No LiveKit API secret, provider key, or static participant token belongs in a `VITE_...` variable because Vite exposes those values to browser code.

## 10. Trust rules

These rules should remain true as the project evolves:

1. SQLite-backed FastAPI responses are the source of application truth.
2. Transcript text is never parsed into business state.
3. LiveKit application messages contain only a type and application ID.
4. The browser refetches authoritative data after a change notification.
5. The LLM cannot manufacture canonical handoff IDs or mutation success.
6. A travel-date change requires deterministic confirmation and backend success.
7. Retries reuse the same idempotency key for the same pending mutation.
8. Secrets and token-signing logic stay on the server.
9. A voice-agent handoff requires the latest finalized user turn to explicitly request a human and uses only `user_request`; rejection occurs before interruption locking or HTTP, so confusion, missing details, corrections, and automatic escalation reasons create no side effect.
