import { describe, expect, it } from 'vitest';
import type { LocalAudioTrack, Room } from 'livekit-client';
import { parseApplicationSignal } from './applicationEvents';
import { LiveKitSessionController } from './livekitSession';
import { upsertTranscriptEntry } from './transcriptReducer';
import {
  deriveVoiceUiState,
  INITIAL_VOICE_SESSION_SNAPSHOT,
  type VoiceTranscriptEntry,
} from './types';

const encoder = new TextEncoder();

function connectedRoomStub(): Room {
  const localParticipant = {
    identity: 'traveler-web',
    publishTrack: async (_track: LocalAudioTrack) => undefined,
    unpublishTrack: async (track: LocalAudioTrack) => {
      track.stop();
    },
  };

  return {
    name: 'waypoint-test-room',
    canPlaybackAudio: true,
    localParticipant,
    remoteParticipants: new Map(),
    connect: async () => undefined,
    disconnect: async () => undefined,
    startAudio: async () => undefined,
    on() {
      return this;
    },
    off() {
      return this;
    },
    registerTextStreamHandler() {},
    unregisterTextStreamHandler() {},
    getParticipantByIdentity() {
      return undefined;
    },
  } as unknown as Room;
}

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

  it('mutes and unmutes the published microphone track, then resets on end', async () => {
    let isMuted = false;
    let microphoneStopped = false;
    let muteCalls = 0;
    let unmuteCalls = 0;
    const microphoneTrack = {
      get isMuted() {
        return isMuted;
      },
      async mute() {
        muteCalls += 1;
        isMuted = true;
      },
      async unmute() {
        unmuteCalls += 1;
        isMuted = false;
      },
      stop() {
        microphoneStopped = true;
      },
    } as unknown as LocalAudioTrack;
    const controller = new LiveKitSessionController({
      roomFactory: connectedRoomStub,
      microphoneTrackFactory: async () => microphoneTrack,
      getToken: async () => ({
        serverUrl: 'wss://voice.example.test',
        participantToken: 'test-token',
      }),
    });

    await controller.start();

    expect(controller.getSnapshot()).toMatchObject({
      transportState: 'connected',
      isMicrophoneMuted: false,
    });

    expect(await controller.toggleMicrophoneMute()).toBe(true);
    expect(muteCalls).toBe(1);
    expect(controller.getSnapshot().isMicrophoneMuted).toBe(true);

    expect(await controller.toggleMicrophoneMute()).toBe(true);
    expect(unmuteCalls).toBe(1);
    expect(controller.getSnapshot().isMicrophoneMuted).toBe(false);

    await controller.toggleMicrophoneMute();
    await controller.end();

    expect(microphoneStopped).toBe(true);
    expect(controller.getSnapshot()).toMatchObject({
      transportState: 'disconnected',
      isMicrophoneMuted: false,
    });
  });

  it('leaves mute state unchanged when no microphone track is available', async () => {
    const controller = new LiveKitSessionController({
      getToken: async () => {
        throw new Error('not used');
      },
    });

    expect(await controller.toggleMicrophoneMute()).toBe(false);
    expect(controller.getSnapshot().isMicrophoneMuted).toBe(false);
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
