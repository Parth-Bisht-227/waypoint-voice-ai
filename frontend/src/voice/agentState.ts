import type { VoiceAgentState } from './types';

const knownAgentStates = new Set<VoiceAgentState>([
  'connecting',
  'pre-connect-buffering',
  'initializing',
  'idle',
  'listening',
  'thinking',
  'speaking',
  'disconnected',
  'failed',
]);

export function parseAgentState(value: string | undefined): VoiceAgentState {
  if (value && knownAgentStates.has(value as VoiceAgentState)) {
    return value as VoiceAgentState;
  }

  return 'unavailable';
}
