import type {
  VoiceTranscriptEntry,
  VoiceTransportState,
  VoiceUiState,
} from '../voice';
import { SessionControls } from './SessionControls';
import { SpeakingOrb } from './SpeakingOrb';
import { TranscriptDrawer } from './TranscriptDrawer';

export interface VoiceDockProps {
  amplitude: number;
  state: VoiceUiState;
  transportState: VoiceTransportState;
  isMicrophoneMuted: boolean;
  canPlaybackAudio: boolean;
  errorMessage?: string | null;
  transcript: readonly VoiceTranscriptEntry[];
  onStart: () => void;
  onEnd: () => void;
  onToggleMicrophoneMute: () => void;
  onEnableAudio: () => void;
}

const voiceStateLabels: Record<VoiceUiState, string> = {
  idle: 'Ready',
  connecting: 'Connecting',
  listening: 'Listening',
  thinking: 'Thinking',
  speaking: 'Speaking',
  reconnecting: 'Reconnecting',
  error: 'Needs attention',
};

const transportLabels: Record<VoiceTransportState, string> = {
  disconnected: 'Disconnected',
  'requesting-microphone': 'Requesting microphone',
  'requesting-token': 'Authorizing',
  connecting: 'Connecting',
  connected: 'Connected',
  reconnecting: 'Reconnecting',
  disconnecting: 'Disconnecting',
  error: 'Connection error',
};

interface UtteranceDisplay {
  speaker: 'You' | 'Waypoint' | 'Session';
  label: 'Current utterance' | 'Latest utterance' | 'Voice status';
  text: string;
}

function latestTranscriptEntry(
  transcript: readonly VoiceTranscriptEntry[],
): VoiceTranscriptEntry | null {
  for (let index = transcript.length - 1; index >= 0; index -= 1) {
    if (transcript[index].text.trim().length > 0) {
      return transcript[index];
    }
  }

  return null;
}

function emptyUtteranceMessage(
  state: VoiceUiState,
  transportState: VoiceTransportState,
): string {
  switch (transportState) {
    case 'requesting-microphone':
      return 'Waiting for microphone access…';
    case 'requesting-token':
      return 'Preparing a secure voice session…';
    case 'connecting':
      return 'Connecting to Waypoint voice…';
    case 'reconnecting':
      return 'Restoring the voice connection…';
    case 'disconnecting':
      return 'Ending the voice session…';
    case 'disconnected':
      return 'Start a voice session when you are ready.';
    case 'error':
      return 'The voice session needs attention.';
    case 'connected':
      break;
  }

  switch (state) {
    case 'listening':
      return 'Listening for your question…';
    case 'thinking':
      return 'Waypoint is preparing a response…';
    case 'speaking':
      return 'Waypoint is speaking…';
    case 'connecting':
      return 'Waiting for the Waypoint voice agent…';
    case 'reconnecting':
      return 'Restoring the voice connection…';
    case 'error':
      return 'The voice session needs attention.';
    case 'idle':
      return 'The voice session is ready.';
  }
}

function utteranceDisplay(
  state: VoiceUiState,
  transportState: VoiceTransportState,
  transcript: readonly VoiceTranscriptEntry[],
  errorMessage: string | null | undefined,
): UtteranceDisplay {
  if (state === 'error') {
    return {
      speaker: 'Session',
      label: 'Voice status',
      text: errorMessage ?? emptyUtteranceMessage(state, transportState),
    };
  }

  const entry = latestTranscriptEntry(transcript);
  if (entry) {
    return {
      speaker: entry.role === 'user' ? 'You' : 'Waypoint',
      label: entry.final ? 'Latest utterance' : 'Current utterance',
      text: entry.text,
    };
  }

  return {
    speaker: 'Session',
    label: 'Voice status',
    text: emptyUtteranceMessage(state, transportState),
  };
}

export function VoiceDock({
  amplitude,
  state,
  transportState,
  isMicrophoneMuted,
  canPlaybackAudio,
  errorMessage,
  transcript,
  onStart,
  onEnd,
  onToggleMicrophoneMute,
  onEnableAudio,
}: VoiceDockProps) {
  const currentUtterance = utteranceDisplay(
    state,
    transportState,
    transcript,
    errorMessage,
  );

  return (
    <section
      className={'voice-dock voice-dock--' + state}
      id="voice-dock"
      aria-label="Waypoint voice session"
      data-transport-state={transportState}
      tabIndex={-1}
    >
      <div className="voice-dock__main">
        <div className="voice-dock__presence">
          <SpeakingOrb amplitude={amplitude} state={state} />
          <span className="voice-dock__presence-label">
            {voiceStateLabels[state]}
          </span>
        </div>

        <div
          className={'current-utterance current-utterance--' + state}
          aria-live="polite"
          aria-atomic="true"
        >
          <p>
            <span>{currentUtterance.speaker}</span>
            <span aria-hidden="true"> / </span>
            {currentUtterance.label}
          </p>
          <blockquote>{currentUtterance.text}</blockquote>
        </div>

        <SessionControls
          state={state}
          transportState={transportState}
          isMicrophoneMuted={isMicrophoneMuted}
          canPlaybackAudio={canPlaybackAudio}
          onStart={onStart}
          onEnd={onEnd}
          onToggleMicrophoneMute={onToggleMicrophoneMute}
          onEnableAudio={onEnableAudio}
        />
      </div>

      <div className="voice-dock__rail">
        <div
          className={
            'connection-status connection-status--' + transportState
          }
          role="status"
          aria-live="polite"
        >
          <span className="connection-status__signal" aria-hidden="true" />
          <span>Voice link</span>
          <strong>{transportLabels[transportState]}</strong>
        </div>
        <TranscriptDrawer entries={transcript} />
      </div>
    </section>
  );
}
