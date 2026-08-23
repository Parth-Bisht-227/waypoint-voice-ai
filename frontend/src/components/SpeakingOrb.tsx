import type { CSSProperties } from 'react';
import type { VoiceUiState } from '../voice';

export type VoicePresence = VoiceUiState;

export interface SpeakingOrbProps {
  amplitude: number;
  state: VoiceUiState;
}

const presenceLabels: Record<VoiceUiState, string> = {
  idle: 'idle',
  connecting: 'connecting',
  listening: 'listening',
  thinking: 'thinking',
  speaking: 'speaking',
  reconnecting: 'reconnecting',
  error: 'unavailable',
};

export function SpeakingOrb({ amplitude, state }: SpeakingOrbProps) {
  const normalizedAmplitude = Number.isFinite(amplitude)
    ? Math.min(1, Math.max(0, amplitude))
    : 0;
  const style = {
    '--voice-amplitude': normalizedAmplitude,
  } as CSSProperties;

  return (
    <div
      className={'speaking-orb speaking-orb--' + state}
      data-state={state}
      style={style}
      role="img"
      aria-label={'Waypoint voice is ' + presenceLabels[state]}
    >
      <span className="speaking-orb__orbit speaking-orb__orbit--outer" />
      <span className="speaking-orb__orbit speaking-orb__orbit--inner" />
      <span className="speaking-orb__core">
        <span className="speaking-orb__shadow" />
        <span className="speaking-orb__spark" />
      </span>
    </div>
  );
}
