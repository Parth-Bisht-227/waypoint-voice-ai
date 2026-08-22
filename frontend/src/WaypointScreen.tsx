import { useState } from 'react';
import { ApplicationCard } from './components/ApplicationCard';
import { PixelJourneyCanvas } from './components/PixelJourneyCanvas';
import type { VoicePresence } from './components/SpeakingOrb';
import { VoiceDock } from './components/VoiceDock';
import { WaypointHeader } from './components/WaypointHeader';
import { mockApplicationAdapter } from './data/mockApplicationAdapter';
import { mockTranscript } from './data/mockTranscript';

const application = mockApplicationAdapter.getSnapshot();

const utterances: Record<VoicePresence, { speaker: 'You' | 'Waypoint' | 'Session'; text: string }> = {
  idle: {
    speaker: 'Session',
    text: 'The demo call has ended. Start again when you are ready.',
  },
  listening: {
    speaker: 'You',
    text: 'I want to check what is still missing from my application.',
  },
  speaking: {
    speaker: 'Waypoint',
    text: 'Your Solara application is waiting for one document: a bank statement.',
  },
};

const amplitudes: Record<VoicePresence, number> = {
  idle: 0.08,
  listening: 0.38,
  speaking: 0.72,
};

export function WaypointScreen() {
  const [presence, setPresence] = useState<VoicePresence>('speaking');
  const connected = presence !== 'idle';

  function handleTalk() {
    setPresence((current) => (current === 'listening' ? 'speaking' : 'listening'));
  }

  function handleEnd() {
    setPresence('idle');
  }

  return (
    <div className="waypoint-shell">
      <a className="skip-link" href="#voice-dock">
        Skip to voice controls
      </a>

      <PixelJourneyCanvas />
      <div className="waypoint-shell__frame" aria-hidden="true" />

      <WaypointHeader routeLabel={`Night route / ${application.destination}`} />

      <main className="waypoint-stage">
        <section className="waypoint-hero" aria-labelledby="waypoint-title">
          <p className="waypoint-hero__eyebrow">Voice travel desk · Field test 01</p>
          <h1 id="waypoint-title" aria-label="Waypoint">
            <span>Way</span>
            <span>point</span>
          </h1>
          <p className="waypoint-hero__lede">
            Ask what is next. Hear one clear answer.
          </p>
        </section>

        <ApplicationCard application={application} />
      </main>

      <VoiceDock
        amplitude={amplitudes[presence]}
        presence={presence}
        connected={connected}
        currentUtterance={utterances[presence]}
        transcript={mockTranscript}
        onTalk={handleTalk}
        onEnd={handleEnd}
      />
    </div>
  );
}

