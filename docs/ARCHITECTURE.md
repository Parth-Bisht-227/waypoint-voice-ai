# Architecture

## 1. Goal

Waypoint connects probabilistic voice conversation to deterministic application
services without making the transcript or LLM the source of business truth.

- The agent interprets speech, manages the conversation, and selects tools.
- FastAPI validates requests and owns persistent state.
- SQLite generates or stores canonical application and handoff records.
- The React client owns browser media and refetches authoritative data.
- Curated local knowledge grounds general and Japan visa answers.
- Session reports make provider and conversation behavior inspectable.

## 2. Current topology

~~~mermaid
flowchart TB
    User((User))

    subgraph Browser["Browser — Vite, React, TypeScript"]
        Screen[WaypointScreen]
        VoiceHook[useVoiceSession]
        Controller[LiveKitSessionController]
        AppHook[useApplication]
        Controls[Talk / Mute / End]
        Canvas[PixelJourneyCanvas]
    end

    subgraph Voice["Realtime voice plane"]
        Room[LiveKit room]
        Agent[waypoint-agent]
        STT[Deepgram Nova-3 multi]
        LLM[Gemini → Cerebras fallback]
        TTS[Cartesia Sonic 3.5]
    end

    subgraph Business["Business and knowledge plane"]
        API[FastAPI]
        DB[(SQLite)]
        Knowledge[knowledge/faqs.json]
    end

    Reports[observability/reports/*.json]

    User <--> Screen
    Screen --> VoiceHook --> Controller
    Screen --> AppHook --> API
    Screen --> Controls
    Canvas -. decorative only .-> Screen
    Controller -->|short-lived token| API
    Controller <--> Room <--> Agent
    Agent --> STT
    Agent --> LLM
    Agent --> TTS
    Agent -->|typed tools| API
    Agent --> Knowledge
    Agent --> Reports
    API <--> DB
    Agent -. canonical ID only .-> Controller
~~~

## 3. Runtime planes

### 3.1 Realtime conversation

LiveKit transports the published microphone track, remote agent audio,
participant attributes, text streams, and application notifications.

~~~mermaid
flowchart LR
    Mic[Microphone] --> RoomIn[LiveKit room]
    RoomIn --> STT[Deepgram STT]
    STT --> LLM[Gemini / Cerebras]
    LLM --> Tool[Typed tool]
    Tool --> API[FastAPI or local retriever]
    API --> Tool --> LLM
    LLM --> TTS[Cartesia TTS]
    TTS --> RoomOut[LiveKit room]
    RoomOut --> Speaker[Browser audio]
~~~

Silero VAD answers whether voice-like audio is present. LiveKit's turn detector
decides whether a conversational turn has ended. The browser derives simple UI
states from LiveKit transport state and the official
<code>lk.agent.state</code> participant attribute.

Fixed endpointing uses a 0.6-second minimum and 2.5-second maximum delay.
Preemptive generation is disabled to avoid discarded provider work on cancelled
turns.

### 3.2 Business data

Both the agent and browser call FastAPI. Only FastAPI reads or writes SQLite.

~~~mermaid
flowchart LR
    AgentTool[Agent HTTP tool] --> API[FastAPI]
    ReactAdapter[React typed adapter] --> API
    API <--> DB[(SQLite)]
    API --> AgentTool
    API --> ReactAdapter --> Card[Application card]
~~~

Transcript text is never parsed into the card's application ID, date, status,
or missing documents.

### 3.3 Knowledge

General Waypoint policies and curated Japan visa guidance share one compact JSON
corpus and one cached lexical retriever. This is intentionally simpler than a
vector database:

1. normalize and tokenize the query;
2. enforce required or exclusive query terms;
3. score exact question, phrase, token, and curated keyword overlap;
4. return one compact answer plus optional source metadata;
5. return no result below the threshold.

The LLM explains only the returned information. It does not use live web search.

### 3.4 Decorative UI

<code>PixelJourneyCanvas</code> owns an isolated animation loop. It has no
connection to tool execution or business progress. It pauses on hidden tabs,
supports a visible pause button, responds to resize, and draws a static frame
under reduced-motion preferences.

## 4. Browser ownership

~~~mermaid
flowchart TB
    Screen[WaypointScreen]
    Screen --> Card[ApplicationCard]
    Screen --> Dock[VoiceDock]
    Screen --> Canvas[PixelJourneyCanvas]
    Dock --> Controls[SessionControls]
    Dock --> Orb[SpeakingOrb]
    Dock --> Transcript[TranscriptDrawer]
    Screen --> AppHook[useApplication]
    Screen --> VoiceHook[useVoiceSession]
    VoiceHook --> Controller[LiveKitSessionController]
    Controller --> Room[Room + microphone + remote audio]
~~~

| Layer | Owns |
| --- | --- |
| <code>WaypointScreen</code> | Page composition and current application ID |
| <code>useApplication</code> | Loading, ready, not-found, error, abort, and refetch state |
| API/domain adapters | Runtime validation and wire-to-domain conversion |
| <code>useVoiceSession</code> | Stable React subscription and controller actions |
| <code>LiveKitSessionController</code> | Room, microphone track, audio, events, transcript, mute state, cleanup |
| UI components | Accessible controls and presentation |
| <code>PixelJourneyCanvas</code> | Decorative motion only |

### Voice-session lifecycle

~~~mermaid
sequenceDiagram
    actor User
    participant UI as SessionControls
    participant C as LiveKitSessionController
    participant API as FastAPI
    participant Room as LiveKit room
    participant Agent as waypoint-agent

    User->>UI: Talk to Waypoint
    UI->>C: start()
    C->>C: createLocalAudioTrack()
    C->>API: POST /voice/token
    API-->>C: URL + scoped token
    C->>Room: connect and publish microphone
    Room->>Agent: named dispatch
    Agent-->>Room: state, transcript, audio, ID hints
    Room-->>C: realtime events

    User->>UI: Mute / Unmute
    UI->>C: toggleMicrophoneMute()
    C->>C: mute() or unmute() same track

    User->>UI: End call
    UI->>C: end()
    C->>Room: unpublish and disconnect
    C->>C: stop track, audio, analyser, listeners
~~~

Concurrent start/end operations are serialized. Token requests can be aborted.
Failure and disconnect paths stop tracks, detach audio and listeners, clear
mute state, and leave a retryable UI state. Browser autoplay blocking exposes
an <code>Enable audio</code> action.

## 5. Provider construction and recovery

The agent creates one fixed LLM chain:

~~~text
Gemini gemini-3.5-flash-lite
        ↓ eligible failure before output/tool execution
Cerebras gpt-oss-120b
~~~

The fallback adapter uses:

- a 12-second attempt timeout;
- zero per-provider retries;
- a short retry interval internal to the adapter;
- no provider switch once chunks or tool calls have been sent.

The same chain is used by the provider-backed evals. The STT, TTS, tools,
backend, and frontend do not change when fallback occurs.

A separate error listener speaks a short retry request only when the entire
configured LLM source emits a terminal non-recoverable error. Generic latency
fillers are not scheduled.

## 6. Multilingual session

The speech pipeline starts as:

~~~text
Deepgram: nova-3, language=multi
Cartesia: sonic-3.5, Parker voice, language=en
Session state: active_language=en
~~~

When the caller explicitly asks for Hindi/Hinglish or clearly begins a complete
request in it:

1. the LLM calls <code>set_spoken_language(language="hi")</code>;
2. the tool updates Cartesia with <code>language="hi"</code>;
3. session state becomes <code>hi</code>;
4. the tool returns a natural-Hinglish reply style;
5. the LLM keeps common travel terms in English/Latin script.

The reverse call switches Cartesia and state back to English. Tool names,
arguments, dates, IDs, destinations, and stored values remain canonical
regardless of spoken language.

Deepgram code-switching is probabilistic. A VAD interruption with no usable
transcript may be classified as a false interruption and resumed by LiveKit.

## 7. Agent tools

The final agent exposes eight tools:

1. <code>set_spoken_language</code>
2. <code>create_travel_application</code>
3. <code>get_application_status</code>
4. <code>get_missing_documents</code>
5. <code>prepare_travel_date_change</code>
6. <code>apply_pending_travel_date_change</code>
7. <code>handoff_to_human</code>
8. <code>search_support_knowledge</code>

Application identifiers are normalized into the current
<code>APP###</code> form before existing-record operations.

### New application

~~~mermaid
sequenceDiagram
    actor User
    participant Agent
    participant API as FastAPI
    participant DB as SQLite
    participant UI as React

    User->>Agent: Create an application
    Agent->>User: Ask only for missing destination/date
    Agent->>User: Summarize and request confirmation
    User->>Agent: Natural confirmation
    Agent->>API: POST /applications
    API->>DB: BEGIN IMMEDIATE, allocate APP number, INSERT
    DB-->>API: committed record
    API-->>Agent: canonical application
    Agent-->>UI: ID-only application_context
    UI->>API: authoritative GETs
~~~

The backend rejects a blank destination, today/past date, extra request fields,
or exhausted three-digit ID capacity. New records begin in
<code>processing</code>.

### Travel-date change

~~~mermaid
stateDiagram-v2
    [*] --> NoPending
    NoPending --> Prepared: valid application + future date
    Prepared --> Prepared: corrected proposal
    Prepared --> Applying: LLM interprets later confirmation
    Applying --> NoPending: backend success
    Applying --> Prepared: timeout or uncertain result
~~~

Preparation verifies the application and stores a canonical ID, proposed date,
and idempotency key in <code>WaypointSessionState</code>. Apply refuses to run
without that pending state. The prompt requires a later natural confirmation;
there is no separate transcript phrase classifier.

The backend transaction checks idempotency, verifies the application, updates
the date, stores the serialized result, and commits. A timeout leaves pending
state intact so a retry reuses the same key.

### Human support

The voice tool accepts only <code>reason_code="user_request"</code>, and its
instructions require an explicit request for a person. FastAPI validates the
application and creates a durable <code>HOF-...</code> request with status
<code>requested</code>. This is not a live transfer.

## 8. Application notifications

After selected successful application tools, the agent publishes on
<code>waypoint.application</code>:

~~~json
{
  "type": "application_context",
  "application_id": "APP004"
}
~~~

or:

~~~json
{
  "type": "application_updated",
  "application_id": "APP004"
}
~~~

The browser accepts only an agent sender, the expected topic, an exact two-key
payload, a known type, and a valid ID. It then refetches FastAPI. Business
fields never travel in the notification.

## 9. Persistence

FastAPI initializes four SQLite tables:

~~~mermaid
erDiagram
    APPLICATIONS ||--o{ MISSING_DOCUMENTS : has
    APPLICATIONS ||..o{ HANDOFF_REQUESTS : receives
    APPLICATIONS ||..o{ IDEMPOTENCY_RECORDS : referenced_by

    APPLICATIONS {
        text application_id PK
        text destination
        text status
        text travel_date
    }
    MISSING_DOCUMENTS {
        text application_id PK, FK
        text document_code PK
    }
    IDEMPOTENCY_RECORDS {
        text idempotency_key PK
        text operation
        text application_id
        text requested_value
        text response_json
        text created_at
    }
    HANDOFF_REQUESTS {
        text handoff_id PK
        text application_id FK
        text reason_code
        text status
        text created_at
    }
~~~

<code>missing_documents</code> uses a composite primary key over
<code>application_id</code> and <code>document_code</code>. Its application ID
and the one in <code>handoff_requests</code> are declared foreign keys.
<code>idempotency_records.application_id</code> is a logical reference used by
the update workflow, but the current SQLite schema does not declare it as a
foreign key.

Seed inserts use <code>INSERT OR IGNORE</code>, so restarting does not overwrite
existing local mutations.

## 10. Observability and boundaries

Session observers log available turn metrics and cumulative provider usage.
When a session ends, the report writer stores formatted JSON under the ignored
<code>observability/reports/</code> directory. Reports may contain transcript
content and require private handling.

The architecture deliberately does not provide:

- real visa adjudication or live requirements;
- airline search, booking, pricing, payment, or ticketing;
- authentication or per-application authorization;
- production rate limiting, TLS/origin policy, secret deployment, or retention;
- deterministic guarantees about LLM wording, multilingual STT, TTS accent, or
  interruption detection.

These boundaries keep the local prototype understandable while still
demonstrating a complete realtime, tool-using, persistent voice application.
