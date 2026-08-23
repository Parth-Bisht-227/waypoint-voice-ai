# Blog preparation notes

Use this as a writing guide, not as a finished post. The detailed engineering
facts live in [the case study](../project.md), while this document suggests a
clear narrative for readers who have not seen the repository.

## Recommended angle

**Working title:** *A Voice Agent Can Sound Right and Still Do the Wrong Thing*

**Thesis:** Realtime voice quality matters, but durable business operations
should not depend solely on an LLM following a prompt. Waypoint combines a
probabilistic conversation layer with deterministic confirmation, handoff,
idempotency, grounding, and UI trust boundaries.

Alternative titles:

- *From Fluent to Reliable: Building a Guarded LiveKit Voice Agent*
- *What a Real Voice Session Taught Me About LLM Tool Safety*
- *Designing Voice AI Where Python Owns the Side Effects*

## Suggested article structure

### 1. Start with the hidden failure

Open with the recorded regression: the assistant prepared a date change,
received `confirmation_required`, called apply in the same tool loop, changed
SQLite, and only then asked the user to confirm. The spoken conversation sounded
reasonable, but the tool trace showed unsafe ordering.

This gives the article a concrete question: how do you keep a conversational
system natural without letting probabilistic routing authorize durable effects?

### 2. Introduce the deliberately small product

Waypoint is a synthetic travel-application assistant. It reads application
status and missing documents, changes a future travel date, answers grounded
support questions, and creates an explicit human-support request.

Keep this section short. The interesting work is reliability, not the size of
the database.

### 3. Explain the architecture in three planes

1. LiveKit carries realtime audio, transcript, and participant state.
2. The Python agent uses Deepgram STT, Groq tool routing, and Cartesia TTS.
3. FastAPI and SQLite own business validation and persistence; the React UI
   refetches authoritative state after receiving an ID-only signal.

Use the Mermaid diagram from [ARCHITECTURE.md](./ARCHITECTURE.md) or redraw it
as one clean image. Emphasize that neither assistant prose nor transcript text
is trusted application state.

### 4. Show prepare, confirm, apply

Explain why `max_tool_steps=3` was not itself the bug. Multiple tool steps are
useful; the unsafe part was allowing apply without independently provable
consent.

Describe the V1 invariant:

```text
complete ID + date
  -> prepare without mutation
  -> ask once
  -> later finalized affirmative turn
  -> deterministic Python gate
  -> one idempotent FastAPI update
```

Mention that later vetoes and replacement dates reset consent. Natural phrases
such as “Yeah, please change it” work, while “okay,” “yes but wait,” and a new
date do not authorize the update.

### 5. Explain the handoff lesson

A later session showed that an LLM could interpret an incomplete date as a
clarification failure and create a handoff too early. The final tool accepts
only `user_request`, checks the latest finalized transcript with a deterministic
explicit-request classifier, and rejects before HTTP or interruption locking.

This is a useful general lesson: a prompt describes policy, but a state-changing
tool must enforce its own authorization boundary.

### 6. Show how observability changed the diagnosis

The session report records conversation items, tools, provider metrics, usage,
state transitions, and shutdown. It established that:

- the unsafe apply happened before the spoken confirmation;
- later End-call behavior closed normally with `participant_disconnected`;
- one choppy call was not caused by a leaked previous room;
- in the final call, provider/backend latency was reasonable and answer length
  contributed more to perceived delay.

Do not publish raw reports without review because they contain transcript text.

### 7. Separate deterministic tests from behavioral evals

Use the final evidence table:

| Layer | Verified result |
| --- | --- |
| Provider-free Python | 145 passed |
| Groq-backed agent flows | 7 passed with all six tools mocked |
| Frontend unit tests | 10 passed |
| TypeScript and Vite build | Passed |
| Real custom-UI call | Status, prepare/confirm/apply, card refresh, handoff, and clean disconnect exercised |

Explain why all six tools are mocked in Groq evals: LiveKit intercepts only the
mapped tools, so a partial map could accidentally reach FastAPI and mutate the
development database.

### 8. Report latency honestly

For the final recorded session, seven measured assistant turns had:

- `1.849s` median and `1.959s` maximum end-to-end latency;
- `0.471s` median steady-state LLM time to first token;
- `0.094s` median TTS time to first audio.

Label these as one-call diagnostic measurements, not a benchmark. Median spoken
output was about `4.72s`, which explains why shorter answers can improve the
experience more than swapping a fast model based on this sample alone.

### 9. Close with deliberate tradeoffs

- The demo is local and uses synthetic records.
- Preemptive generation is disabled to reduce discarded Groq requests under
  the current quota.
- Public source is safe to separate from public deployment; the runtime still
  lacks authentication, authorization, rate limits, and production retention.
- Deterministic APP-ID speech formatting, accessibility QA, browser E2E, bundle
  splitting, and deployment hardening remain valid V1.1 work.

End with the principle: **probabilistic language handles the conversation;
deterministic code owns business truth and side effects.**

### Optional provider-cost note

The eight retained local session reports account for `3,498` Cartesia
characters and `242.80s` of generated audio across 48 assistant replies. That
is only the usage visible in saved reports: earlier/deleted reports, sessions
that failed before shutdown reporting, playground use, and other projects on
the same account are not represented. Use the provider dashboard—not this
partial local total—as the billing source of truth.

## Visuals to prepare

1. One architecture diagram showing browser, LiveKit, agent/providers,
   FastAPI, and SQLite.
2. One screenshot with the live transcript and APP004 card visible.
3. A compact prepare-confirm-apply sequence diagram.
4. Optionally, a redacted report excerpt showing tool ordering and latency.

Do not show environment files, API keys, signed tokens, raw unreviewed reports,
or local filesystem paths in the published article.

## Claims to avoid

- Do not call the system production-ready or secure for real traveler data.
- Do not present one session's latency as a benchmark or SLA.
- Do not claim exact LLM wording, routing, STT, or pronunciation is deterministic.
- Do not say the frontend is deployed merely because the source is public.
- Do not imply the handoff tool guarantees a notification or response time.

## Best source files while writing

1. [project.md](../project.md) — concise engineering case study and failure story.
2. [ARCHITECTURE.md](./ARCHITECTURE.md) — diagrams and trust boundaries.
3. [CURRENT_STATUS.md](./CURRENT_STATUS.md) — verified results and limitations.
4. [DEMO_GUIDE.md](./DEMO_GUIDE.md) — the final spoken demo sequence.
5. [CONTRACTS.md](./CONTRACTS.md) — exact HTTP, state, and event details when
   a technical claim needs checking.
