# Portfolio demo recording guide

Use this runbook for a short, evidence-led recording of the local Waypoint
system. It is intentionally smaller than the full acceptance checklist in
[LOCAL_DEVELOPMENT.md](./LOCAL_DEVELOPMENT.md).

Before the clean database reset below, optionally run the focused handoff smoke
from the local-development guide: incomplete date, confusion, and an
informational support-agent question must produce zero handoff POSTs; a later
explicit request must produce exactly one. Reset afterward because the
successful handoff is durable, and start the recording with clean logs.

## What the recording should prove

In one connected session, show that spoken input can select an application,
prepare and safely confirm a date change, refresh authoritative backend state,
request a human explicitly, and shut down cleanly. Generated wording is
provider-variable: judge each turn by the tool and UI behavior below, not by an
exact assistant sentence.

## Prepare a clean take

1. Stop FastAPI before touching its database. The seed operation uses
   `INSERT OR IGNORE`, so restarting alone does not undo earlier demo changes.
2. Confirm the file you are about to move:

   ```powershell
   Resolve-Path -LiteralPath .\backend\waypoint.db
   ```

3. Give the existing development database a recoverable, unused backup name:

   ```powershell
   Move-Item -LiteralPath .\backend\waypoint.db -Destination .\backend\waypoint.pre-demo.db
   ```

   Both files match the repository's `*.db` ignore rule. Do not use this reset
   against a database containing non-synthetic data.
4. Start FastAPI again and verify the fresh `APP004` seed:

   ```powershell
   Invoke-RestMethod http://127.0.0.1:8000/applications/APP004
   ```

   It should be `approved`, with destination `Norvik` and travel date
   `2026-11-12`.
5. Start `waypoint-agent` and Vite, then wait until all three processes are
   ready. Keep only one browser voice session connected.
6. Verify the recorder captures both the microphone and system/agent audio with
   a short disposable clip. Prefer headphones to prevent echo.
7. Warm the stack with one short private status turn if needed, then end that
   call and wait for `DISCONNECTED` before recording. Do not run the
   provider-backed Groq evals immediately before the take; the demo should have
   a fresh token budget.
8. Hide `.env` files, signed tokens, provider dashboards, and terminal output
   containing credentials. Session reports can contain transcript text and
   should be inspected before they appear on screen.

## 75–90 second recording script

| Time | Action or exact user line | Expected semantics and visible evidence |
| --- | --- | --- |
| 0–5s | Show the Waypoint screen and title. | Brief overlay: `Voice → LiveKit → Python agent → FastAPI/SQLite`. |
| 5–13s | Press **Talk to Waypoint** and let the greeting finish. | The link connects; listening/thinking/speaking state, transcript, and remote-audio orb become live. |
| 13–25s | “What's the status of A P P zero zero four?” | The status tool reads `APP004`; the card changes from `APP001` to the authoritative `APP004` record and the assistant gives a brief approved/date answer. |
| 25–40s | “Change A P P zero zero four to December fifteenth, twenty twenty-seven.” | The agent prepares the change and asks one short confirmation. The date has not changed and no PATCH has occurred yet. |
| 40–52s | “Yeah, please change it.” | The deterministic confirmation gate permits exactly one PATCH. The assistant reports success only after FastAPI succeeds, and the ID-only update signal causes the card to refetch and show `2027-12-15`. |
| 52–65s | “I want to speak to a human about A P P zero zero four.” | The explicit opt-in permits exactly one handoff request with reason `user_request`; the assistant confirms only after the backend succeeds. |
| 65–74s | Press **End call**. | The room disconnects and microphone, audio, analyser/orb, and connected state stop. |
| 74–90s | Cut briefly to evidence. | Show the updated card, one PATCH and one handoff POST in FastAPI logs, then the newest report filename with normal participant disconnect and no shutdown error. |

The assistant may phrase the answers differently. Good semantic shapes are a
short status sentence, one question containing the canonical application and
prepared date, a short completion sentence, and a short handoff result. Do not
claim that exact pronunciation, response wording, or timing is deterministic.

## Avoid a failed take

- Let the assistant finish each response. Speaking over it exercises
  interruption handling and can introduce pause/resume artifacts that distract
  from this short story.
- Say the whole application ID, month, day, and year in one utterance. The
  selected 2027 date is deliberately later than every seed date.
- Keep the call short. Long histories and repeated rehearsals can approach the
  current Groq quota and produce retries or silent delays.
- Use a stable network, headphones, and a foreground browser tab. Close the
  LiveKit Playground and duplicate Waypoint tabs before recording.
- If audio breaks into chunks, end the call cleanly and compare one short turn
  in the LiveKit UI. A smooth LiveKit UI with a choppy custom UI points toward
  browser playback; both being choppy points upstream. Record the custom UI
  only after one clean rehearsal.
- If Groq chooses a different conversational path, restart the take rather
  than editing out a misleading sequence. Tool routing and natural-language
  realization are behavioral eval targets, not deterministic guarantees.

## Evidence and post-record checks

Before keeping the take, verify:

- the recording contains both sides of the audio and readable UI text;
- the card visibly switches to `APP004` and later shows `2027-12-15`;
- FastAPI shows no date PATCH before confirmation, exactly one successful PATCH
  after it, and exactly one handoff POST after the explicit request;
- ending the call stops the microphone and returns the UI to disconnected;
- the newest ignored report was saved, has a normal
  `participant_disconnected` close reason, and records no shutdown error;
- no secret, signed participant token, `.env` content, or unreviewed transcript
  appears in the video;
- `git status` does not offer the database, reports, dependency folders, or
  build output for commit.

Keep the pre-demo database backup until the recording is approved. Restoring it
is optional for this synthetic project, but stop FastAPI before moving database
files in either direction.
