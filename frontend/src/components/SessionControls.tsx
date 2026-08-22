import type { VoicePresence } from './SpeakingOrb';

interface SessionControlsProps {
  presence: VoicePresence;
  connected: boolean;
  onTalk: () => void;
  onEnd: () => void;
}

function MicrophoneIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 15.5a4 4 0 0 0 4-4V6a4 4 0 1 0-8 0v5.5a4 4 0 0 0 4 4Z" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v4M8.5 22h7" />
    </svg>
  );
}

function EndCallIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 15.5c3.9-3.3 10.1-3.3 14 0M5 15.5l2.5 3 2.8-2.1M19 15.5l-2.5 3-2.8-2.1" />
    </svg>
  );
}

export function SessionControls({
  presence,
  connected,
  onTalk,
  onEnd,
}: SessionControlsProps) {
  const talkLabel =
    presence === 'listening'
      ? 'Listening…'
      : connected
        ? 'Talk to Waypoint'
        : 'Start again';

  return (
    <div className="session-controls" role="group" aria-label="Voice session controls">
      <button
        className="session-control session-control--talk"
        type="button"
        onClick={onTalk}
        aria-pressed={presence === 'listening'}
      >
        <MicrophoneIcon />
        <span>{talkLabel}</span>
      </button>

      <button
        className="session-control session-control--end"
        type="button"
        onClick={onEnd}
        disabled={!connected}
      >
        <EndCallIcon />
        <span>End call</span>
      </button>
    </div>
  );
}

