import {
  createLocalAudioTrack,
  RemoteAudioTrack,
  Room,
  RoomEvent,
  Track,
  type LocalAudioTrack,
  type Participant,
  type RemoteParticipant,
  type RemoteTrack,
  type RemoteTrackPublication,
  type TextStreamReader,
} from 'livekit-client';
import { parseAgentState } from './agentState';
import { parseApplicationSignal } from './applicationEvents';
import { RemoteAudioLevelMonitor } from './audioLevel';
import { upsertTranscriptEntry } from './transcriptReducer';
import {
  AGENT_STATE_ATTRIBUTE,
  APPLICATION_EVENT_TOPIC,
  INITIAL_VOICE_SESSION_SNAPSHOT,
  TRANSCRIPTION_TOPIC,
  type ApplicationSignal,
  type VoiceConnectionCredentials,
  type VoiceSessionError,
  type VoiceSessionSnapshot,
  type VoiceTokenProvider,
  type VoiceTranscriptRole,
} from './types';

type SnapshotListener = () => void;

export interface LiveKitSessionControllerOptions {
  getToken: VoiceTokenProvider;
  onApplicationSignal?: (signal: ApplicationSignal) => void;
  onReconnected?: () => void;
  roomFactory?: () => Room;
  microphoneTrackFactory?: () => Promise<LocalAudioTrack>;
  transcriptLimit?: number;
  amplitudeIntervalMs?: number;
}

const PUBLIC_ERROR_MESSAGES: Record<VoiceSessionError['code'], string> = {
  'microphone-denied':
    'Microphone access was denied. Allow access in your browser and try again.',
  'microphone-unavailable':
    'No usable microphone is available. Check your device and try again.',
  'token-failed':
    'Waypoint could not start a secure voice session. Please try again.',
  'connection-failed':
    'Waypoint could not connect to the voice room. Please try again.',
  'connection-lost':
    'The voice connection ended unexpectedly. Please start a new call.',
  unexpected: 'Something interrupted the voice session. Please try again.',
};

function microphoneErrorCode(
  error: unknown,
): 'microphone-denied' | 'microphone-unavailable' {
  if (
    error instanceof DOMException &&
    (error.name === 'NotAllowedError' || error.name === 'SecurityError')
  ) {
    return 'microphone-denied';
  }

  return 'microphone-unavailable';
}

function validateCredentials(
  credentials: VoiceConnectionCredentials,
): VoiceConnectionCredentials {
  let parsedUrl: URL;

  try {
    parsedUrl = new URL(credentials.serverUrl);
  } catch {
    throw new Error('The token endpoint returned an invalid LiveKit URL.');
  }

  if (
    (parsedUrl.protocol !== 'wss:' && parsedUrl.protocol !== 'ws:') ||
    credentials.participantToken.trim().length === 0
  ) {
    throw new Error('The token endpoint returned invalid voice credentials.');
  }

  return credentials;
}

export class LiveKitSessionController {
  private snapshot: VoiceSessionSnapshot = INITIAL_VOICE_SESSION_SNAPSHOT;
  private readonly listeners = new Set<SnapshotListener>();
  private readonly getToken: VoiceTokenProvider;
  private readonly onApplicationSignal?: (signal: ApplicationSignal) => void;
  private readonly onReconnected?: () => void;
  private readonly roomFactory: () => Room;
  private readonly microphoneTrackFactory: () => Promise<LocalAudioTrack>;
  private readonly transcriptLimit: number;
  private readonly amplitudeIntervalMs: number;

  private room: Room | null = null;
  private microphoneTrack: LocalAudioTrack | null = null;
  private remoteAudioTrack: RemoteAudioTrack | null = null;
  private remoteAudioElement: HTMLAudioElement | null = null;
  private audioLevelMonitor: RemoteAudioLevelMonitor | null = null;
  private agentIdentity: string | null = null;
  private roomListenerCleanup: Array<() => void> = [];
  private textHandlerRoom: Room | null = null;
  private tokenAbortController: AbortController | null = null;
  private operationId = 0;
  private startPromise: Promise<void> | null = null;
  private endPromise: Promise<void> | null = null;

  constructor({
    getToken,
    onApplicationSignal,
    onReconnected,
    roomFactory = () => new Room(),
    microphoneTrackFactory = () =>
      createLocalAudioTrack({
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      }),
    transcriptLimit = 100,
    amplitudeIntervalMs = 80,
  }: LiveKitSessionControllerOptions) {
    this.getToken = getToken;
    this.onApplicationSignal = onApplicationSignal;
    this.onReconnected = onReconnected;
    this.roomFactory = roomFactory;
    this.microphoneTrackFactory = microphoneTrackFactory;
    this.transcriptLimit = transcriptLimit;
    this.amplitudeIntervalMs = amplitudeIntervalMs;
  }

  getSnapshot = (): VoiceSessionSnapshot => this.snapshot;

  subscribe = (listener: SnapshotListener): (() => void) => {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  };

  start = (): Promise<void> => {
    if (this.startPromise) {
      return this.startPromise;
    }

    const pendingEnd = this.endPromise;
    if (
      !pendingEnd &&
      this.snapshot.transportState !== 'disconnected' &&
      this.snapshot.transportState !== 'error'
    ) {
      return Promise.resolve();
    }

    const promise = (pendingEnd ?? Promise.resolve()).then(() =>
      this.performStart(),
    );
    this.startPromise = promise;

    void promise.finally(() => {
      if (this.startPromise === promise) {
        this.startPromise = null;
      }
    });

    return promise;
  };

  end = (): Promise<void> => {
    if (this.endPromise) {
      return this.endPromise;
    }

    const operationId = ++this.operationId;
    this.startPromise = null;
    this.tokenAbortController?.abort();

    if (
      this.snapshot.transportState !== 'disconnected' ||
      this.room ||
      this.microphoneTrack
    ) {
      this.updateSnapshot({
        transportState: 'disconnecting',
        agentState: 'unavailable',
        error: null,
      });
    }

    const promise = this.cleanupResources().then(() => {
      if (this.operationId === operationId) {
        this.updateSnapshot({
          transportState: 'disconnected',
          agentState: 'unavailable',
          amplitude: 0,
          canPlaybackAudio: true,
          error: null,
          roomName: null,
          participantIdentity: null,
        });
      }
    });
    this.endPromise = promise;

    void promise.finally(() => {
      if (this.endPromise === promise) {
        this.endPromise = null;
      }
    });

    return promise;
  };

  enableAudio = async (): Promise<boolean> => {
    const room = this.room;

    if (!room) {
      return false;
    }

    try {
      await room.startAudio();
      if (this.room !== room) {
        return false;
      }

      const canPlaybackAudio = room.canPlaybackAudio;
      this.updateSnapshot({ canPlaybackAudio });
      return canPlaybackAudio;
    } catch {
      if (this.room === room) {
        this.updateSnapshot({ canPlaybackAudio: false });
      }
      return false;
    }
  };

  clearTranscript = (): void => {
    if (this.snapshot.transcript.length > 0) {
      this.updateSnapshot({ transcript: [] });
    }
  };

  destroy = async (): Promise<void> => {
    this.listeners.clear();
    await this.end();
  };

  private async performStart(): Promise<void> {
    const operationId = ++this.operationId;
    let phase: 'microphone' | 'token' | 'connection' = 'microphone';

    this.updateSnapshot({
      transportState: 'requesting-microphone',
      agentState: 'unavailable',
      transcript: [],
      amplitude: 0,
      canPlaybackAudio: true,
      error: null,
      roomName: null,
      participantIdentity: null,
    });

    try {
      const microphoneTrack = await this.microphoneTrackFactory();

      if (this.operationId !== operationId) {
        microphoneTrack.stop();
        return;
      }

      this.microphoneTrack = microphoneTrack;
      phase = 'token';
      this.updateSnapshot({ transportState: 'requesting-token' });

      const tokenAbortController = new AbortController();
      this.tokenAbortController = tokenAbortController;
      const credentials = validateCredentials(
        await this.getToken(tokenAbortController.signal),
      );

      if (this.operationId !== operationId) {
        return;
      }

      this.tokenAbortController = null;
      phase = 'connection';
      this.updateSnapshot({ transportState: 'connecting' });

      const room = this.roomFactory();
      this.room = room;
      this.registerRoomHandlers(room, operationId);
      this.registerTranscriptionHandler(room, operationId);

      await room.connect(credentials.serverUrl, credentials.participantToken);

      if (this.operationId !== operationId) {
        return;
      }

      await room.localParticipant.publishTrack(microphoneTrack, {
        source: Track.Source.Microphone,
      });

      if (this.operationId !== operationId) {
        return;
      }

      this.updateSnapshot({
        transportState: 'connected',
        roomName: room.name || credentials.roomName || null,
        participantIdentity:
          room.localParticipant.identity ||
          credentials.participantIdentity ||
          null,
        canPlaybackAudio: room.canPlaybackAudio,
      });

      for (const participant of room.remoteParticipants.values()) {
        if (participant.isAgent) {
          this.synchronizeAgent(participant, operationId);
          break;
        }
      }

      void this.enableAudio();
    } catch (error) {
      if (this.operationId !== operationId) {
        return;
      }

      const errorCode =
        phase === 'microphone'
          ? microphoneErrorCode(error)
          : phase === 'token'
            ? 'token-failed'
            : 'connection-failed';

      await this.cleanupResources();

      if (this.operationId === operationId) {
        this.updateSnapshot({
          transportState: 'error',
          agentState: 'unavailable',
          amplitude: 0,
          canPlaybackAudio: true,
          error: {
            code: errorCode,
            message: PUBLIC_ERROR_MESSAGES[errorCode],
          },
          roomName: null,
          participantIdentity: null,
        });
      }
    }
  }

  private registerRoomHandlers(room: Room, operationId: number): void {
    const isCurrentRoom = () =>
      this.operationId === operationId && this.room === room;

    const onReconnecting = () => {
      if (isCurrentRoom()) {
        this.updateSnapshot({ transportState: 'reconnecting' });
      }
    };

    const onReconnected = () => {
      if (isCurrentRoom()) {
        this.updateSnapshot({
          transportState: 'connected',
          canPlaybackAudio: room.canPlaybackAudio,
        });
        this.onReconnected?.();
      }
    };

    const onDisconnected = () => {
      if (!isCurrentRoom()) {
        return;
      }

      const cleanupOperationId = ++this.operationId;
      void this.cleanupResources().then(() => {
        if (this.operationId === cleanupOperationId) {
          this.updateSnapshot({
            transportState: 'error',
            agentState: 'disconnected',
            amplitude: 0,
            canPlaybackAudio: true,
            error: {
              code: 'connection-lost',
              message: PUBLIC_ERROR_MESSAGES['connection-lost'],
            },
            roomName: null,
            participantIdentity: null,
          });
        }
      });
    };

    const onParticipantConnected = (participant: RemoteParticipant) => {
      if (isCurrentRoom() && participant.isAgent) {
        this.synchronizeAgent(participant, operationId);
      }
    };

    const onParticipantDisconnected = (participant: RemoteParticipant) => {
      if (
        isCurrentRoom() &&
        participant.isAgent &&
        participant.identity === this.agentIdentity
      ) {
        this.agentIdentity = null;
        this.detachRemoteAudio();
        this.updateSnapshot({ agentState: 'disconnected' });
      }
    };

    const onParticipantAttributesChanged = (
      changedAttributes: Record<string, string>,
      participant: Participant,
    ) => {
      if (
        isCurrentRoom() &&
        participant.isAgent &&
        AGENT_STATE_ATTRIBUTE in changedAttributes
      ) {
        this.agentIdentity = participant.identity;
        this.updateSnapshot({
          agentState: parseAgentState(
            participant.attributes[AGENT_STATE_ATTRIBUTE],
          ),
        });
      }
    };

    const onTrackSubscribed = (
      track: RemoteTrack,
      _publication: RemoteTrackPublication,
      participant: RemoteParticipant,
    ) => {
      if (
        isCurrentRoom() &&
        participant.isAgent &&
        track instanceof RemoteAudioTrack
      ) {
        this.agentIdentity = participant.identity;
        this.attachRemoteAudio(track, operationId);
      }
    };

    const onTrackUnsubscribed = (
      track: RemoteTrack,
      _publication: RemoteTrackPublication,
      participant: RemoteParticipant,
    ) => {
      if (
        isCurrentRoom() &&
        participant.isAgent &&
        track === this.remoteAudioTrack
      ) {
        this.detachRemoteAudio();
      }
    };

    const onAudioPlaybackChanged = () => {
      if (isCurrentRoom()) {
        this.updateSnapshot({ canPlaybackAudio: room.canPlaybackAudio });
      }
    };

    const onDataReceived = (
      payload: Uint8Array,
      participant?: RemoteParticipant,
      _kind?: unknown,
      topic?: string,
    ) => {
      if (
        !isCurrentRoom() ||
        topic !== APPLICATION_EVENT_TOPIC ||
        !participant?.isAgent
      ) {
        return;
      }

      const signal = parseApplicationSignal(payload);
      if (signal) {
        this.onApplicationSignal?.(signal);
      }
    };

    room.on(RoomEvent.Reconnecting, onReconnecting);
    room.on(RoomEvent.Reconnected, onReconnected);
    room.on(RoomEvent.Disconnected, onDisconnected);
    room.on(RoomEvent.ParticipantConnected, onParticipantConnected);
    room.on(RoomEvent.ParticipantDisconnected, onParticipantDisconnected);
    room.on(
      RoomEvent.ParticipantAttributesChanged,
      onParticipantAttributesChanged,
    );
    room.on(RoomEvent.TrackSubscribed, onTrackSubscribed);
    room.on(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed);
    room.on(RoomEvent.AudioPlaybackStatusChanged, onAudioPlaybackChanged);
    room.on(RoomEvent.DataReceived, onDataReceived);

    this.roomListenerCleanup = [
      () => room.off(RoomEvent.Reconnecting, onReconnecting),
      () => room.off(RoomEvent.Reconnected, onReconnected),
      () => room.off(RoomEvent.Disconnected, onDisconnected),
      () => room.off(RoomEvent.ParticipantConnected, onParticipantConnected),
      () =>
        room.off(RoomEvent.ParticipantDisconnected, onParticipantDisconnected),
      () =>
        room.off(
          RoomEvent.ParticipantAttributesChanged,
          onParticipantAttributesChanged,
        ),
      () => room.off(RoomEvent.TrackSubscribed, onTrackSubscribed),
      () => room.off(RoomEvent.TrackUnsubscribed, onTrackUnsubscribed),
      () =>
        room.off(
          RoomEvent.AudioPlaybackStatusChanged,
          onAudioPlaybackChanged,
        ),
      () => room.off(RoomEvent.DataReceived, onDataReceived),
    ];
  }

  private registerTranscriptionHandler(
    room: Room,
    operationId: number,
  ): void {
    room.registerTextStreamHandler(
      TRANSCRIPTION_TOPIC,
      (reader, participantInfo) => {
        void this.consumeTranscription(
          room,
          reader,
          participantInfo.identity,
          operationId,
        );
      },
    );
    this.textHandlerRoom = room;
  }

  private async consumeTranscription(
    room: Room,
    reader: TextStreamReader,
    participantIdentity: string,
    operationId: number,
  ): Promise<void> {
    const attributes = reader.info.attributes ?? {};

    if (!attributes['lk.transcribed_track_id']) {
      return;
    }

    const role = this.transcriptRole(room, participantIdentity);
    if (!role) {
      return;
    }

    const segmentId = attributes['lk.segment_id']?.trim() || reader.info.id;
    const id = `${role}:${participantIdentity}:${segmentId}`;
    const final = attributes['lk.transcription_final'] === 'true';
    const timestamp = Date.now();

    let accumulatedText = '';
    try {
      for await (const text of reader) {
        if (
          this.operationId !== operationId ||
          this.room !== room ||
          text.trim().length === 0
        ) {
          continue;
        }

        accumulatedText += text;

        const transcript = upsertTranscriptEntry(
          this.snapshot.transcript,
          {
            id,
            role,
            text: accumulatedText,
            final,
            timestamp,
            participantIdentity,
          },
          this.transcriptLimit,
        );

        if (transcript !== this.snapshot.transcript) {
          this.updateSnapshot({ transcript });
        }
      }
    } catch {
      // A stream can be interrupted during disconnect; session state owns recovery.
    }
  }

  private transcriptRole(
    room: Room,
    participantIdentity: string,
  ): VoiceTranscriptRole | null {
    if (participantIdentity === room.localParticipant.identity) {
      return 'user';
    }

    const participant = room.getParticipantByIdentity(participantIdentity);
    return participant?.isAgent ? 'assistant' : null;
  }

  private synchronizeAgent(
    participant: RemoteParticipant,
    operationId: number,
  ): void {
    if (
      this.operationId !== operationId ||
      this.room === null ||
      !participant.isAgent
    ) {
      return;
    }

    this.agentIdentity = participant.identity;
    this.updateSnapshot({
      agentState: parseAgentState(
        participant.attributes[AGENT_STATE_ATTRIBUTE],
      ),
    });

    for (const publication of participant.audioTrackPublications.values()) {
      const track = publication.audioTrack;
      if (track instanceof RemoteAudioTrack) {
        this.attachRemoteAudio(track, operationId);
        break;
      }
    }
  }

  private attachRemoteAudio(
    track: RemoteAudioTrack,
    operationId: number,
  ): void {
    if (
      this.operationId !== operationId ||
      this.remoteAudioTrack === track
    ) {
      return;
    }

    this.detachRemoteAudio();
    this.remoteAudioTrack = track;

    if (typeof document !== 'undefined') {
      const audioElement = document.createElement('audio');
      audioElement.autoplay = true;
      audioElement.setAttribute('aria-hidden', 'true');
      audioElement.style.display = 'none';
      track.attach(audioElement);
      document.body.append(audioElement);
      this.remoteAudioElement = audioElement;
    }

    try {
      this.audioLevelMonitor = new RemoteAudioLevelMonitor(track, {
        intervalMs: this.amplitudeIntervalMs,
        onAmplitude: (amplitude) => {
          if (
            this.operationId === operationId &&
            this.remoteAudioTrack === track
          ) {
            this.updateSnapshot({ amplitude });
          }
        },
      });
    } catch {
      this.updateSnapshot({ amplitude: 0 });
    }

    if (this.room) {
      this.updateSnapshot({ canPlaybackAudio: this.room.canPlaybackAudio });
    }
  }

  private detachRemoteAudio(): void {
    this.audioLevelMonitor?.stop();
    this.audioLevelMonitor = null;

    if (this.remoteAudioTrack && this.remoteAudioElement) {
      try {
        this.remoteAudioTrack.detach(this.remoteAudioElement);
      } catch {
        // It may already be detached during SDK track teardown.
      }
    }

    this.remoteAudioElement?.remove();
    this.remoteAudioElement = null;
    this.remoteAudioTrack = null;
    this.updateSnapshot({ amplitude: 0 });
  }

  private async cleanupResources(): Promise<void> {
    this.tokenAbortController?.abort();
    this.tokenAbortController = null;

    const room = this.room;
    const microphoneTrack = this.microphoneTrack;
    this.room = null;
    this.microphoneTrack = null;
    this.agentIdentity = null;

    for (const cleanup of this.roomListenerCleanup.splice(0)) {
      try {
        cleanup();
      } catch {
        // A partially connected room may already have removed it.
      }
    }

    if (this.textHandlerRoom) {
      try {
        this.textHandlerRoom.unregisterTextStreamHandler(
          TRANSCRIPTION_TOPIC,
        );
      } catch {
        // It may already be gone after connection failure.
      }
      this.textHandlerRoom = null;
    }

    this.detachRemoteAudio();

    if (room && microphoneTrack) {
      try {
        await room.localParticipant.unpublishTrack(microphoneTrack, true);
      } catch {
        microphoneTrack.stop();
      }
    } else {
      microphoneTrack?.stop();
    }

    if (room) {
      try {
        await room.disconnect(true);
      } catch {
        // The room can already be fully disconnected after a network failure.
      }
    }
  }

  private updateSnapshot(
    patch: Partial<VoiceSessionSnapshot>,
  ): void {
    const entries = Object.entries(patch) as Array<
      [keyof VoiceSessionSnapshot, VoiceSessionSnapshot[keyof VoiceSessionSnapshot]]
    >;

    if (entries.every(([key, value]) => Object.is(this.snapshot[key], value))) {
      return;
    }

    this.snapshot = { ...this.snapshot, ...patch };
    for (const listener of this.listeners) {
      listener();
    }
  }
}
