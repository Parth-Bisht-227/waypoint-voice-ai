import { useCallback, useEffect, useState } from 'react';
import { DEFAULT_APPLICATION_ID } from './api/config';
import { requestVoiceToken } from './api/voiceToken';
import { ApplicationCard } from './components/ApplicationCard';
import { PixelJourneyCanvas } from './components/PixelJourneyCanvas';
import { VoiceDock } from './components/VoiceDock';
import { WaypointHeader } from './components/WaypointHeader';
import { useApplication } from './hooks/useApplication';
import {
  deriveVoiceUiState,
  type ApplicationSignal,
  type VoiceConnectionCredentials,
  useVoiceSession,
} from './voice';

async function getVoiceCredentials(
  signal: AbortSignal,
): Promise<VoiceConnectionCredentials> {
  const response = await requestVoiceToken(signal);

  return {
    serverUrl: response.server_url,
    participantToken: response.participant_token,
    roomName: response.room_name,
    participantIdentity: response.participant_identity,
  };
}

export function WaypointScreen() {
  const [currentApplicationId, setCurrentApplicationId] = useState(
    DEFAULT_APPLICATION_ID,
  );
  const {
    state: applicationResource,
    refetch: refetchApplication,
  } = useApplication(currentApplicationId);

  const handleApplicationSignal = useCallback(
    (signal: ApplicationSignal) => {
      setCurrentApplicationId(signal.applicationId);
      refetchApplication();
    },
    [refetchApplication],
  );

  const voice = useVoiceSession({
    getToken: getVoiceCredentials,
    onApplicationSignal: handleApplicationSignal,
    onReconnected: refetchApplication,
  });
  const voiceState = deriveVoiceUiState(voice);

  useEffect(() => {
    function refreshVisibleApplication() {
      if (document.visibilityState === 'visible') {
        refetchApplication();
      }
    }

    document.addEventListener('visibilitychange', refreshVisibleApplication);
    return () => {
      document.removeEventListener(
        'visibilitychange',
        refreshVisibleApplication,
      );
    };
  }, [refetchApplication]);

  const routeDestination =
    applicationResource.status === 'ready'
      ? applicationResource.application.destination
      : currentApplicationId;

  return (
    <div className="waypoint-shell">
      <a className="skip-link" href="#voice-dock">
        Skip to voice controls
      </a>

      <PixelJourneyCanvas />
      <div className="waypoint-shell__frame" aria-hidden="true" />

      <WaypointHeader routeLabel={`Night route / ${routeDestination}`} />

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

        <ApplicationCard
          resource={applicationResource}
          onRetry={refetchApplication}
        />
      </main>

      <VoiceDock
        amplitude={voice.amplitude}
        state={voiceState}
        transportState={voice.transportState}
        isMicrophoneMuted={voice.isMicrophoneMuted}
        canPlaybackAudio={voice.canPlaybackAudio}
        errorMessage={voice.error?.message}
        transcript={voice.transcript}
        onStart={() => void voice.start()}
        onEnd={() => void voice.end()}
        onToggleMicrophoneMute={() => void voice.toggleMicrophoneMute()}
        onEnableAudio={() => void voice.enableAudio()}
      />
    </div>
  );
}
