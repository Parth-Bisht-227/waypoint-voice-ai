import type { CSSProperties } from 'react';

export type VoicePresence = 'idle' | 'listening' | 'speaking';

interface SpeakingOrbProps {
  amplitude: number;
  state: VoicePresence;
}

const presenceLabels: Record<VoicePresence, string> = {
  idle: 'idle',
  listening: 'listening',
  speaking: 'speaking',
};

export function SpeakingOrb({ amplitude, state }: SpeakingOrbProps) {
  const normalizedAmplitude = Math.min(1, Math.max(0, amplitude));
  const style = {
    '--voice-amplitude': normalizedAmplitude,
  } as CSSProperties;

  return (
    <div
      className="speaking-orb"
      data-state={state}
      style={style}
      role="img"
      aria-label={`Waypoint voice is ${presenceLabels[state]}`}
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

