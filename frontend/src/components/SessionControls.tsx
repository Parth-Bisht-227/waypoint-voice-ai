import type { VoiceTransportState, VoiceUiState } from '../voice';

export interface SessionControlsProps {
  state: VoiceUiState;
  transportState: VoiceTransportState;
  isMicrophoneMuted: boolean;
  canPlaybackAudio: boolean;
  onStart: () => void;
  onEnd: () => void;
  onToggleMicrophoneMute: () => void;
  onEnableAudio: () => void;
}

function MicrophoneIcon({ muted = false }: { muted?: boolean }) {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 15.5a4 4 0 0 0 4-4V6a4 4 0 1 0-8 0v5.5a4 4 0 0 0 4 4Z" />
      <path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v4M8.5 22h7" />
      {muted ? <path d="m4 4 16 16" /> : null}
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

function SpeakerIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M5 9h4l5-4v14l-5-4H5zM17 9a4 4 0 0 1 0 6M19.5 6.5a7.5 7.5 0 0 1 0 11" />
    </svg>
  );
}

function isActiveTransport(transportState: VoiceTransportState): boolean {
  return (
    transportState === 'requesting-microphone' ||
    transportState === 'requesting-token' ||
    transportState === 'connecting' ||
    transportState === 'connected' ||
    transportState === 'reconnecting' ||
    transportState === 'disconnecting'
  );
}

export function SessionControls({
  state,
  transportState,
  isMicrophoneMuted,
  canPlaybackAudio,
  onStart,
  onEnd,
  onToggleMicrophoneMute,
  onEnableAudio,
}: SessionControlsProps) {
  const active = isActiveTransport(transportState);
  const canStart =
    !active &&
    (state === 'idle' || state === 'error') &&
    (transportState === 'disconnected' || transportState === 'error');
  const ending = transportState === 'disconnecting';
  const connected =
    transportState === 'connected' || transportState === 'reconnecting';
  const playbackBlocked =
    !canPlaybackAudio &&
    (transportState === 'connected' || transportState === 'reconnecting');

  return (
    <div
      className="session-controls"
      role="group"
      aria-label="Voice session controls"
    >
      {canStart ? (
        <button
          className="session-control session-control--talk session-control--start"
          type="button"
          onClick={onStart}
        >
          <MicrophoneIcon />
          <span>
            {state === 'error' ? 'Try voice again' : 'Talk to Waypoint'}
          </span>
        </button>
      ) : null}

      {playbackBlocked ? (
        <button
          className="session-control session-control--audio"
          type="button"
          onClick={onEnableAudio}
        >
          <SpeakerIcon />
          <span>Enable audio</span>
        </button>
      ) : null}

      {connected ? (
        <button
          className="session-control session-control--mute"
          type="button"
          aria-pressed={isMicrophoneMuted}
          onClick={onToggleMicrophoneMute}
        >
          <MicrophoneIcon muted={isMicrophoneMuted} />
          <span>{isMicrophoneMuted ? 'Unmute' : 'Mute'}</span>
        </button>
      ) : null}

      {active ? (
        <button
          className="session-control session-control--end"
          type="button"
          onClick={onEnd}
          disabled={ending}
        >
          <EndCallIcon />
          <span>{ending ? 'Ending…' : 'End call'}</span>
        </button>
      ) : null}
    </div>
  );
}
