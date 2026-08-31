# Runtime and data contracts

Snapshot: 2026-08-31. Use the latest Git revision for exact code.

## 1. URL convention

The frontend calls relative <code>/api/...</code> paths. During development,
Vite proxies them to <code>http://127.0.0.1:8000</code> and removes the
<code>/api</code> prefix.

| Browser request | FastAPI receives |
| --- | --- |
| <code>/api/applications/APP001</code> | <code>/applications/APP001</code> |
| <code>/api/applications/APP001/missing-documents</code> | <code>/applications/APP001/missing-documents</code> |
| <code>/api/voice/token</code> | <code>/voice/token</code> |

A deployed frontend would need equivalent gateway routing.

## 2. FastAPI endpoints

The API is unauthenticated and intended only for synthetic local data.

### Create an application

~~~http
POST /applications
Content-Type: application/json
~~~

Request:

~~~json
{
  "destination": "Japan",
  "travel_date": "2027-04-15"
}
~~~

Successful <code>201</code> response:

~~~json
{
  "application_id": "APP005",
  "destination": "Japan",
  "status": "processing",
  "travel_date": "2027-04-15"
}
~~~

Rules:

- only <code>destination</code> and <code>travel_date</code> are accepted;
- destination is trimmed, must not be blank, and is limited to 80 characters;
- travel date must be later than the backend's current date;
- the backend starts <code>BEGIN IMMEDIATE</code>, reads the highest numeric
  <code>APP</code> suffix, allocates the next three-digit ID, inserts, and
  commits;
- capacity beyond <code>APP999</code> returns <code>503</code>;
- validation errors return <code>400</code> or Pydantic's <code>422</code>.

The endpoint creates an internal Waypoint support record, not a booking or visa
submission.

### Read an application

~~~http
GET /applications/{application_id}
~~~

~~~json
{
  "application_id": "APP001",
  "destination": "Solara",
  "status": "blocked",
  "travel_date": "2026-09-10"
}
~~~

Known records return <code>200</code>; unknown IDs return <code>404</code>.

### Read missing documents

~~~http
GET /applications/{application_id}/missing-documents
~~~

~~~json
{
  "application_id": "APP001",
  "missing_documents": ["bank_statement"]
}
~~~

A known application with no missing documents returns an empty list. An unknown
application returns <code>404</code>.

### Update a travel date

~~~http
PATCH /applications/{application_id}/travel-date
Content-Type: application/json
~~~

~~~json
{
  "new_date": "2027-12-20",
  "idempotency_key": "date-session-generated-key"
}
~~~

Successful response:

~~~json
{
  "application_id": "APP001",
  "old_date": "2026-09-10",
  "new_date": "2027-12-20",
  "changed": true
}
~~~

Rules:

- today or a past date returns <code>400</code>;
- an unknown application returns <code>404</code>;
- the first key use stores the requested operation and serialized result in the
  same transaction as the update;
- the identical retry returns the stored result without another update;
- reusing a key for a different logical request returns <code>409</code>.

Conversational confirmation lives in the agent prompt and separate
prepare/apply tool flow. The public endpoint itself does not authenticate the
caller or inspect a transcript.

### Create a human-support request

~~~http
POST /applications/{application_id}/handoffs
Content-Type: application/json
~~~

~~~json
{
  "reason_code": "user_request"
}
~~~

Successful <code>201</code> response:

~~~json
{
  "handoff_id": "HOF-a1b2c3d4e5",
  "application_id": "APP001",
  "reason_code": "user_request",
  "status": "requested"
}
~~~

FastAPI creates the handoff ID. This is a durable request record, not a live
transfer.

### Issue a voice token

~~~http
POST /voice/token
~~~

~~~json
{
  "server_url": "wss://example.livekit.cloud",
  "participant_token": "<short-lived signed token>",
  "room_name": "waypoint-unique-room",
  "participant_identity": "browser-unique-identity"
}
~~~

Contract:

- token lifetime is 10 minutes;
- room and browser identity are unique;
- the grant permits join, subscription, and microphone-source publication;
- data publication is disabled;
- room configuration dispatches <code>waypoint-agent</code>;
- success and failure responses use <code>Cache-Control: no-store</code>;
- invalid configuration or minting failure returns a generic <code>503</code>;
- no reusable token or provider credential is sent to the browser.

## 3. Domain enums

Application status:

~~~text
processing
approved
blocked
action_required
~~~

Backend handoff reasons:

~~~text
user_request
unsupported_request
repeated_clarification_failure
backend_failure
state_conflict
critical_entity_uncertain
~~~

The backend retains the complete enum. The current voice tool exposes only
<code>user_request</code>.

Handoff status:

~~~text
requested
~~~

## 4. LiveKit browser protocol

The browser uses <code>livekit-client</code> 2.22.0.

### Media

- <code>createLocalAudioTrack()</code> requests echo cancellation, noise
  suppression, and automatic gain control.
- The local track is published as <code>Track.Source.Microphone</code>.
- Remote audio is accepted only from a participant marked as an agent.
- The remote agent track feeds both playback and the normalized speaking-orb
  analyser.

### Microphone mute

<code>toggleMicrophoneMute()</code> operates on the existing local track:

- unmuted → await <code>track.mute()</code>;
- muted → await <code>track.unmute()</code>;
- snapshot state is read from <code>track.isMuted</code>;
- no available track returns <code>false</code> without inventing a state;
- start, disconnect, failure, and cleanup reset
  <code>isMicrophoneMuted</code> to <code>false</code>.

The connected UI exposes one accessible Mute/Unmute button with
<code>aria-pressed</code>.

### Agent state

Official participant attribute:

~~~text
lk.agent.state
~~~

Recognized values:

~~~text
connecting
pre-connect-buffering
initializing
idle
listening
thinking
speaking
disconnected
failed
~~~

Unknown or absent values become internal <code>unavailable</code>. Transport
failure and reconnecting take precedence in the simpler UI state.

### Transcription

Text-stream topic:

~~~text
lk.transcription
~~~

| Attribute | Meaning |
| --- | --- |
| <code>lk.transcribed_track_id</code> | Required track-transcription marker |
| <code>lk.segment_id</code> | Stable ID for interim/final replacement |
| <code>lk.transcription_final</code> | String <code>true</code> marks a final segment |

Only the local participant maps to <code>user</code> and only an agent
participant maps to <code>assistant</code>.

## 5. Application refresh messages

Topic:

~~~text
waypoint.application
~~~

Allowed payloads:

~~~json
{
  "type": "application_context",
  "application_id": "APP005"
}
~~~

~~~json
{
  "type": "application_updated",
  "application_id": "APP001"
}
~~~

The browser requires:

- the expected topic;
- an agent sender;
- a UTF-8 payload from 1 to 4,096 bytes;
- exactly <code>type</code> and <code>application_id</code>;
- a recognized type and valid ID.

It then refetches FastAPI. Any payload containing status, date, destination, or
documents is rejected.

The agent emits <code>application_context</code> after successful application
creation/read/document lookup/date preparation. Only a confirmed successful
PATCH emits <code>application_updated</code>.

## 6. Agent session and tool contracts

Per-session state:

~~~text
active_language = en | hi
pending_application_id = APP### | None
pending_travel_date = YYYY-MM-DD | None
pending_idempotency_key = generated string | None
application_signal_sender = callable | None
~~~

Eight tool names are stable:

~~~text
set_spoken_language
create_travel_application
get_application_status
get_missing_documents
prepare_travel_date_change
apply_pending_travel_date_change
handoff_to_human
search_support_knowledge
~~~

Application tools use canonical dates and IDs.
<code>apply_pending_travel_date_change</code> cannot begin without prepared
state. Durable create/update tools disable interruption around the external
write.

The language tool accepts only <code>en</code> or <code>hi</code>, updates the
active Cartesia TTS language, and returns both active language and expected reply
style. Hindi mode means natural Hinglish by default unless the caller asks for
pure Hindi. Tool data remains canonical.

## 7. Speech/provider contract

~~~text
STT: Deepgram nova-3, language=multi
LLM primary: Gemini gemini-3.5-flash-lite
LLM fallback: Cerebras gpt-oss-120b
TTS: Cartesia sonic-3.5
Voice: 30894953-bcce-41fe-892c-15ce19c843ff (Parker)
Initial TTS language: en
~~~

LLM attempt timeout is 12 seconds with no per-provider retry. Fallback is
disabled after a response chunk or tool call has begun. Generic normal-turn
latency fillers are not used. A terminal recovery message is spoken only when
the complete configured LLM source fails non-recoverably.

## 8. Knowledge contract

<code>knowledge/faqs.json</code> contains compact support and visa entries.
Visa entries may include:

~~~text
official_source
source_url
last_reviewed
required_query_terms
exclusive_query_terms
~~~

The current verified visa scope is:

- ordinary Indian passport holder;
- residing and applying from India;
- short-term tourism;
- Japan only.

The retriever returns one compact answer and optional source metadata or:

~~~json
{
  "found": false
}
~~~

There is no vector database or live search.

## 9. Frontend application boundary

React consumes:

~~~ts
interface ApplicationSnapshot {
  applicationId: string;
  destination: string;
  status: 'processing' | 'approved' | 'blocked' | 'action_required';
  travelDate: string;
  missingDocuments: readonly string[];
}
~~~

The adapter validates IDs, matching responses, known status, real
<code>YYYY-MM-DD</code> dates, and string document codes. Malformed responses
become controlled service errors.

## 10. SQLite schema and seeds

Database path:

~~~text
backend/waypoint.db
~~~

| Table | Key | Purpose |
| --- | --- | --- |
| <code>applications</code> | <code>application_id</code> | Authoritative application records |
| <code>missing_documents</code> | <code>(application_id, document_code)</code> | Recorded missing document codes |
| <code>idempotency_records</code> | <code>idempotency_key</code> | Stored logical date-update results |
| <code>handoff_requests</code> | <code>handoff_id</code> | Durable human-support requests |

Initial synthetic seeds:

| ID | Destination | Status | Travel date | Missing documents |
| --- | --- | --- | --- | --- |
| <code>APP001</code> | Solara | blocked | 2026-09-10 | bank_statement |
| <code>APP002</code> | Solara | processing | 2026-10-05 | none |
| <code>APP003</code> | Norvik | action_required | 2026-09-28 | passport_scan |
| <code>APP004</code> | Norvik | approved | 2026-11-12 | none |

Seeds use <code>INSERT OR IGNORE</code>; a previously mutated local database may
differ.

## 11. Configuration

Ignored server-side file: <code>agent/.env.local</code>.

| Variable | Purpose |
| --- | --- |
| <code>LIVEKIT_URL</code> | LiveKit deployment URL |
| <code>LIVEKIT_API_KEY</code> | Server/agent LiveKit credential |
| <code>LIVEKIT_API_SECRET</code> | Server/agent LiveKit credential |
| <code>DEEPGRAM_API_KEY</code> | STT |
| <code>GOOGLE_API_KEY</code> | Gemini primary |
| <code>CEREBRAS_API_KEY</code> | Cerebras fallback |
| <code>CARTESIA_API_KEY</code> | TTS |
| <code>BACKEND_BASE_URL</code> | Agent-to-FastAPI URL; defaults to localhost:8000 |

Optional browser-visible configuration:

| Variable | Purpose |
| --- | --- |
| <code>VITE_DEFAULT_APPLICATION_ID</code> | Initial card ID; defaults to APP001 |

Provider secrets and LiveKit signing credentials must never use a
<code>VITE_</code> prefix.

## 12. Trust rules

1. FastAPI/SQLite responses are authoritative application state.
2. Transcript text is never parsed into business state.
3. LiveKit application messages contain only a type and application ID.
4. The browser refetches the API after a valid notification.
5. The model cannot generate canonical application or handoff success.
6. Date updates require prepared state, a future date, backend success, and an
   idempotency key.
7. Natural confirmation and explicit-handoff intent are LLM workflow behavior,
   not authentication.
8. Unsupported knowledge returns no result rather than invented policy.
9. Language switching changes spoken rendering, not stored/tool data.
10. Secrets and token signing remain server-side.
