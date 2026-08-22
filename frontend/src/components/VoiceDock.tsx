import type { TranscriptEntry } from '../data/mockTranscript';
import type { VoicePresence } from './SpeakingOrb';
import { SessionControls } from './SessionControls';
import { SpeakingOrb } from './SpeakingOrb';
import { TranscriptDrawer } from './TranscriptDrawer';

interface CurrentUtterance {
  speaker: 'You' | 'Waypoint' | 'Session';
  text: string;
}

interface VoiceDockProps {
  amplitude: number;
  presence: VoicePresence;
  connected: boolean;
  currentUtterance: CurrentUtterance;
  transcript: readonly TranscriptEntry[];
  onTalk: () => void;
  onEnd: () => void;
}

export function VoiceDock({
  amplitude,
  presence,
  connected,
  currentUtterance,
  transcript,
  onTalk,
  onEnd,
}: VoiceDockProps) {
  const connectionLabel = connected ? 'Connected' : 'Call ended';

  return (
    <section
      className="voice-dock"
      id="voice-dock"
      aria-label="Waypoint voice session"
      tabIndex={-1}
    >
      <div className="voice-dock__main">
        <div className="voice-dock__presence">
          <SpeakingOrb amplitude={amplitude} state={presence} />
          <span className="voice-dock__presence-label">Voice presence</span>
        </div>

        <div className="current-utterance" aria-live="polite" aria-atomic="true">
          <p>
            <span>{currentUtterance.speaker}</span>
            <span aria-hidden="true"> / </span>
            Current utterance
          </p>
          <blockquote>{currentUtterance.text}</blockquote>
        </div>

        <SessionControls
          presence={presence}
          connected={connected}
          onTalk={onTalk}
          onEnd={onEnd}
        />
      </div>

      <div className="voice-dock__rail">
        <div className="connection-status" role="status" aria-live="polite">
          <span className="connection-status__signal" aria-hidden="true" />
          <span>Demo voice link</span>
          <strong>{connectionLabel}</strong>
        </div>
        <TranscriptDrawer entries={transcript} />
      </div>
    </section>
  );
}

