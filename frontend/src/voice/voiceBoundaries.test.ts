import { describe, expect, it } from 'vitest';
import type { LocalAudioTrack } from 'livekit-client';
import { parseApplicationSignal } from './applicationEvents';
import { LiveKitSessionController } from './livekitSession';
import { upsertTranscriptEntry } from './transcriptReducer';
import {
  deriveVoiceUiState,
  INITIAL_VOICE_SESSION_SNAPSHOT,
  type VoiceTranscriptEntry,
} from './types';

const encoder = new TextEncoder();

function entry(
  overrides: Partial<VoiceTranscriptEntry> = {},
): VoiceTranscriptEntry {
  return {
    id: 'assistant:agent:segment-1',
    role: 'assistant',
    text: 'Your application',
    final: false,
    timestamp: 1,
    participantIdentity: 'agent-waypoint',
    ...overrides,
  };
}

describe('voice presentation boundaries', () => {
  it('accepts only typed ID-only application signals', () => {
    expect(
      parseApplicationSignal(
        encoder.encode(
          JSON.stringify({
            type: 'application_updated',
            application_id: 'APP001',
          }),
        ),
      ),
    ).toEqual({
      type: 'application_updated',
      applicationId: 'APP001',
    });

    expect(
      parseApplicationSignal(
        encoder.encode(
          JSON.stringify({
            type: 'application_updated',
            application_id: 'APP001',
            travel_date: '2030-01-01',
          }),
        ),
      ),
    ).toBeNull();
  });

  it('reconciles interim and final transcript segments without duplicates', () => {
    const interim = upsertTranscriptEntry([], entry());
    const finalized = upsertTranscriptEntry(
      interim,
      entry({
        text: 'Your application is ready.',
        final: true,
        timestamp: 99,
      }),
    );
    const staleInterim = upsertTranscriptEntry(
      finalized,
      entry({ text: 'Your application is', final: false }),
    );

    expect(finalized).toHaveLength(1);
    expect(finalized[0]).toMatchObject({
      text: 'Your application is ready.',
      final: true,
      timestamp: 1,
    });
    expect(staleInterim).toBe(finalized);
  });

  it('surfaces a current token timeout and releases the microphone', async () => {
    let microphoneStopped = false;
    const microphoneTrack = {
      stop() {
        microphoneStopped = true;
      },
    } as unknown as LocalAudioTrack;
    const controller = new LiveKitSessionController({
      microphoneTrackFactory: async () => microphoneTrack,
      getToken: async () => {
        throw new DOMException('Token request timed out', 'TimeoutError');
      },
    });

    await controller.start();

    expect(controller.getSnapshot()).toMatchObject({
      transportState: 'error',
      error: {
        code: 'token-failed',
      },
    });
    expect(microphoneStopped).toBe(true);
  });

  it('gives transport failures and reconnection precedence in UI state', () => {
    expect(
      deriveVoiceUiState({
        ...INITIAL_VOICE_SESSION_SNAPSHOT,
        transportState: 'reconnecting',
        agentState: 'speaking',
      }),
    ).toBe('reconnecting');

    expect(
      deriveVoiceUiState({
        ...INITIAL_VOICE_SESSION_SNAPSHOT,
        transportState: 'error',
        agentState: 'listening',
      }),
    ).toBe('error');

    expect(
      deriveVoiceUiState({
        ...INITIAL_VOICE_SESSION_SNAPSHOT,
        transportState: 'connected',
        agentState: 'unavailable',
      }),
    ).toBe('connecting');
  });
});
