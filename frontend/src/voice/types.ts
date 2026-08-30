export const AGENT_STATE_ATTRIBUTE = 'lk.agent.state';
export const TRANSCRIPTION_TOPIC = 'lk.transcription';
export const APPLICATION_EVENT_TOPIC = 'waypoint.application';

export type VoiceTransportState =
  | 'disconnected'
  | 'requesting-microphone'
  | 'requesting-token'
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnecting'
  | 'error';

export type LiveKitAgentState =
  | 'connecting'
  | 'pre-connect-buffering'
  | 'initializing'
  | 'idle'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'disconnected'
  | 'failed';

export type VoiceAgentState = LiveKitAgentState | 'unavailable';

export type VoiceTranscriptRole = 'user' | 'assistant';

export interface VoiceTranscriptEntry {
  id: string;
  role: VoiceTranscriptRole;
  text: string;
  final: boolean;
  timestamp: number;
  participantIdentity: string;
}

export type ApplicationSignalType =
  | 'application_context'
  | 'application_updated';

export interface ApplicationSignal {
  type: ApplicationSignalType;
  applicationId: string;
}

export interface VoiceConnectionCredentials {
  serverUrl: string;
  participantToken: string;
  roomName?: string;
  participantIdentity?: string;
}

export type VoiceTokenProvider = (
  signal: AbortSignal,
) => Promise<VoiceConnectionCredentials>;

export type VoiceSessionErrorCode =
  | 'microphone-denied'
  | 'microphone-unavailable'
  | 'token-failed'
  | 'connection-failed'
  | 'connection-lost'
  | 'unexpected';

export interface VoiceSessionError {
  code: VoiceSessionErrorCode;
  message: string;
}

export interface VoiceSessionSnapshot {
  transportState: VoiceTransportState;
  agentState: VoiceAgentState;
  transcript: readonly VoiceTranscriptEntry[];
  amplitude: number;
  isMicrophoneMuted: boolean;
  canPlaybackAudio: boolean;
  error: VoiceSessionError | null;
  roomName: string | null;
  participantIdentity: string | null;
}

export type VoiceUiState =
  | 'idle'
  | 'connecting'
  | 'listening'
  | 'thinking'
  | 'speaking'
  | 'reconnecting'
  | 'error';

export const INITIAL_VOICE_SESSION_SNAPSHOT: VoiceSessionSnapshot = {
  transportState: 'disconnected',
  agentState: 'unavailable',
  transcript: [],
  amplitude: 0,
  isMicrophoneMuted: false,
  canPlaybackAudio: true,
  error: null,
  roomName: null,
  participantIdentity: null,
};

export function deriveVoiceUiState(
  snapshot: VoiceSessionSnapshot,
): VoiceUiState {
  if (
    snapshot.transportState === 'error' ||
    snapshot.agentState === 'failed'
  ) {
    return 'error';
  }

  if (snapshot.transportState === 'reconnecting') {
    return 'reconnecting';
  }

  if (
    snapshot.transportState === 'requesting-microphone' ||
    snapshot.transportState === 'requesting-token' ||
    snapshot.transportState === 'connecting'
  ) {
    return 'connecting';
  }

  if (snapshot.transportState !== 'connected') {
    return 'idle';
  }

  switch (snapshot.agentState) {
    case 'speaking':
      return 'speaking';
    case 'thinking':
      return 'thinking';
    case 'listening':
      return 'listening';
    case 'connecting':
    case 'pre-connect-buffering':
    case 'initializing':
    case 'disconnected':
    case 'unavailable':
      return 'connecting';
    default:
      return 'idle';
  }
}

export function isVoiceSessionConnected(
  snapshot: VoiceSessionSnapshot,
): boolean {
  return (
    snapshot.transportState === 'connected' ||
    snapshot.transportState === 'reconnecting'
  );
}
