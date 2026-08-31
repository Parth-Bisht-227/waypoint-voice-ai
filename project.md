# Waypoint Voice Lab — engineering case study

## Summary

Waypoint is a full-stack voice AI travel-support prototype built to demonstrate
how realtime conversation can be connected to typed tools and durable state
without treating model-generated prose as business truth.

A caller can create or inspect a synthetic application, check missing
documents, change a future travel date after confirmation, request human
support, and ask grounded questions about Japan tourist-visa preparation. The
same call can switch between English and natural Hindi/Hinglish.

The project is intentionally a local reference prototype. It has no airline
inventory, payments, government submission, user authentication, or live human
transfer.

## The engineering problem

A voice application crosses several probabilistic boundaries:

- the microphone and VAD may treat speech as noise or noise as speech;
- multilingual STT may misrecognize short or code-switched phrases;
- an LLM may choose the wrong tool or produce an overly long spoken answer;
- providers may time out or exhaust quota;
- a fluent answer may hide an incorrectly ordered side effect;
- transcript text and data messages are unsafe sources of UI business state.

Waypoint makes those boundaries visible and gives deterministic services
ownership of the facts that matter.

## System design

~~~mermaid
flowchart LR
    Browser[React voice UI] <--> Room[LiveKit room]
    Room <--> Agent[Python voice agent]
    Agent --> Speech[Deepgram STT + Cartesia TTS]
    Agent --> Models[Gemini → Cerebras]
    Agent --> API[FastAPI tools]
    Browser -->|authoritative reads| API
    API <--> SQLite[(SQLite)]
    Agent --> Knowledge[Curated FAQ + Japan visa data]
    Agent -. application ID only .-> Browser
    Agent --> Reports[Local session reports]
~~~

Three data planes stay separate:

1. **Realtime conversation:** LiveKit carries microphone audio, agent audio,
   transcripts, participant state, and application notifications.
2. **Business data:** FastAPI validates typed requests and owns all SQLite reads
   and writes.
3. **UI synchronization:** the agent publishes only a canonical application ID;
   React validates it and refetches FastAPI before rendering.

## Final feature set

### Voice experience

The React client owns the LiveKit room and published microphone track outside
the component render lifecycle. It handles token acquisition, microphone
permission, connection, reconnecting, remote audio, transcripts, cleanup, and
autoplay recovery.

Mute/unmute calls <code>mute()</code> and <code>unmute()</code> on the existing
local audio track. It does not recreate the track or reconnect the room.

Deepgram Nova-3 runs with <code>language="multi"</code>. The session starts in
English. A typed <code>set_spoken_language</code> tool changes Cartesia between
English and Hindi output and records the active language in session state.
Hindi mode defaults to natural Hinglish while preserving familiar travel terms
in Latin script.

### Provider fallback

The agent constructs a fixed LiveKit fallback chain:

1. Gemini <code>gemini-3.5-flash-lite</code>
2. Cerebras <code>gpt-oss-120b</code>

Each provider has a bounded connection timeout and no per-provider retry. The
adapter does not switch after streamed content or a tool call has started,
reducing the risk of duplicate speech or repeated durable operations. A
separate terminal failure handler speaks a short recovery message only if the
whole configured chain fails.

### Synthetic application workflows

FastAPI supports:

- creating an application from a destination and future travel date;
- reading status, destination, and travel date;
- reading missing documents;
- applying an idempotent travel-date update;
- creating a durable human-support request.

The backend generates canonical <code>APP###</code> and
<code>HOF-...</code> identifiers. The model never invents a successful result.

New-application and date-change conversations ask for only missing details,
summarize the proposal once, and wait for natural confirmation before calling
the creation or apply tool. The date-change implementation keeps a prepared
application ID, date, and idempotency key in per-session state.

The conversational confirmation decision is intentionally handled by the
prompt and LLM rather than a large phrase classifier. Deterministic protection
still exists at the data boundary: dates must be in the future, pending state
must exist before apply, backend errors cannot be presented as success, and
retries of the same date mutation return the transactionally stored result.

### Grounded support and visa guidance

One cached lexical retriever serves compact answers from
<code>knowledge/faqs.json</code>. It scores exact questions, phrase and token
overlap, curated keywords, required destination terms, and exclusive visa
queries. Unsupported questions return a no-result response rather than a
plausible invention.

Visa coverage is deliberately limited to short-term Japan tourism for an
ordinary Indian passport holder who resides and applies in India. The entries
include official Embassy/VFS links and review dates. Spoken answers cover only
the question asked and remind the caller to verify current requirements.

## Failures that shaped the implementation

### Model-side confirmation was initially unsafe

An early provider-backed call prepared a travel-date change and then attempted
the apply tool within the same tool loop. The project first responded with a
large deterministic confirmation grammar. That protected the mutation but
made normal voice conversation rigid and difficult to maintain.

The final design keeps the separate prepare/apply tools, session pending state,
backend future-date validation, transactional idempotency, focused prompt
instructions, and behavioral evals. It removes the large phrase grammar and
documents the resulting boundary honestly: natural confirmation is model
behavior, while data validity and retry safety are code-owned.

### Generic latency fillers queued behind real answers

A custom two-second timer called <code>session.say()</code> whenever the agent
was still marked as thinking. Reports showed that the main reply already owned
the earlier speech position, so the filler could be synthesized and played
after the real answer—especially when that answer was long.

The generic filler was removed. Current tools are local or use short backend
timeouts, so the UI thinking state is sufficient. If a future external tool is
genuinely slow, LiveKit's tool-scoped filler context is the appropriate place
to add progress speech.

### One LLM provider was not enough for longer calls

The earlier Groq setup repeatedly hit its free-tier token-per-minute limit in
long conversations. Moving to Gemini with Cerebras fallback separated the
application from one provider's quota and demonstrated LiveKit's bounded
fallback behavior. A real call showed Gemini fail over to Cerebras and later
recover, without changing the tools, STT, TTS, backend, or frontend.

### Hindi interruption exposed an acoustic/STT boundary

Multilingual calls proved that the model and TTS can produce useful Hinglish.
They also showed that short Hindi speech spoken over agent audio may trigger
VAD without producing a usable Deepgram transcript. LiveKit then correctly
classifies the event as a false interruption and resumes the answer.

This is treated as a provider/acoustic limitation, not hidden with application
logic. Headphones, clear phrases, and suitable microphone capture help; keyterm
prompting and voice isolation remain optional experiments rather than committed
complexity.

## Observability

Every completed agent session writes an ignored JSON report containing:

- chat and tool-call ordering;
- agent and user state transitions;
- transcription, LLM, and TTS usage;
- available end-of-turn, first-token, first-audio, and end-to-end metrics;
- interruption and false-interruption events;
- close reason and terminal error state.

Reports were used to distinguish provider fallback from total failure, detect
queued filler speech, confirm tool outputs, inspect multilingual transcripts,
and verify clean participant disconnects. They may contain conversation text
and must remain private.

## Verification evidence

Snapshot date: 2026-08-31.

| Evidence | Result |
| --- | --- |
| Provider-free Python suite | 80 passed |
| Provider-backed agent-flow evals | 8 scenarios collect successfully |
| Frontend unit suite | 14 passed across 4 files |
| TypeScript check and Vite build | Passed |
| Latest multilingual live call | Four tool calls, English/Hinglish switching, grounded application and Japan guidance, no generic filler speech, clean disconnect |
| Fallback live call | Gemini primary, Cerebras fallback, and later Gemini recovery observed |

Provider-backed evals and human calls remain variable and are intentionally
reported separately from deterministic unit and backend tests.

## Tradeoffs and limitations

- SQLite and synthetic records keep persistence understandable but are not a
  production identity or authorization system.
- Natural confirmation and handoff intent are LLM-governed workflow behavior;
  backend validation and idempotency do not replace authentication.
- The visa corpus is curated, narrow, and dated instead of broad or live.
- Explicit runtime language switching is more predictable than automatic
  per-sentence TTS switching.
- Deepgram code-switching and interruptions can vary with accent, phrasing,
  overlap, and microphone conditions.
- Preemptive generation is disabled to avoid wasted provider work on cancelled
  turns.
- Session reports are useful locally but need a retention and redaction policy
  before any real deployment.
- The current frontend bundle is large because LiveKit ships in the initial
  path; code splitting remains an optional engineering follow-up.

## Engineering outcomes

- A complete realtime STT → LLM/tools → TTS application.
- Full-stack coordination between LiveKit, React, FastAPI, and SQLite.
- Typed tool and HTTP boundaries around probabilistic model behavior.
- Transactional idempotency for a durable voice-triggered mutation.
- Runtime provider fallback without rewriting the application workflow.
- Curated lexical grounding without a vector database.
- English/Hindi/Hinglish voice switching with canonical tool data.
- Evidence-led debugging through session reports and focused evals.
- Intentional scope control: useful travel-support workflows without presenting
  the prototype as a booking or government visa platform.

## Conclusion

Waypoint combines realtime voice interaction with explicit system boundaries:
LiveKit carries audio, Deepgram and Cartesia handle speech, Gemini with
Cerebras fallback drives conversation and typed tool selection, and FastAPI
with SQLite owns durable application state. A compact lexical retriever grounds
support and Japan visa answers, while tests, provider-backed evals, and session
reports provide evidence about behavior across deterministic and probabilistic
parts of the system.

See [the README](./README.md) for setup and
[the architecture document](./docs/ARCHITECTURE.md) for detailed runtime
boundaries.
