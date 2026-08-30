import {
  useCallback,
  useEffect,
  useRef,
  useSyncExternalStore,
} from 'react';
import {
  LiveKitSessionController,
  type LiveKitSessionControllerOptions,
} from './livekitSession';
import type {
  ApplicationSignal,
  VoiceSessionSnapshot,
  VoiceTokenProvider,
} from './types';

export interface UseVoiceSessionOptions
  extends Omit<
    LiveKitSessionControllerOptions,
    'getToken' | 'onApplicationSignal' | 'onReconnected'
  > {
  getToken: VoiceTokenProvider;
  onApplicationSignal?: (signal: ApplicationSignal) => void;
  onReconnected?: () => void;
}

export interface UseVoiceSessionResult extends VoiceSessionSnapshot {
  start: () => Promise<void>;
  end: () => Promise<void>;
  toggleMicrophoneMute: () => Promise<boolean>;
  enableAudio: () => Promise<boolean>;
  clearTranscript: () => void;
}

export function useVoiceSession({
  getToken,
  onApplicationSignal,
  onReconnected,
  ...controllerOptions
}: UseVoiceSessionOptions): UseVoiceSessionResult {
  const getTokenRef = useRef(getToken);
  const applicationSignalRef = useRef(onApplicationSignal);
  const reconnectedRef = useRef(onReconnected);
  getTokenRef.current = getToken;
  applicationSignalRef.current = onApplicationSignal;
  reconnectedRef.current = onReconnected;

  const controllerRef = useRef<LiveKitSessionController | null>(null);
  if (!controllerRef.current) {
    controllerRef.current = new LiveKitSessionController({
      ...controllerOptions,
      getToken: (signal) => getTokenRef.current(signal),
      onApplicationSignal: (signal) =>
        applicationSignalRef.current?.(signal),
      onReconnected: () => reconnectedRef.current?.(),
    });
  }

  const controller = controllerRef.current;
  const snapshot = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
    controller.getSnapshot,
  );

  useEffect(
    () => () => {
      void controller.destroy();
    },
    [controller],
  );

  const start = useCallback(() => controller.start(), [controller]);
  const end = useCallback(() => controller.end(), [controller]);
  const toggleMicrophoneMute = useCallback(
    () => controller.toggleMicrophoneMute(),
    [controller],
  );
  const enableAudio = useCallback(
    () => controller.enableAudio(),
    [controller],
  );
  const clearTranscript = useCallback(
    () => controller.clearTranscript(),
    [controller],
  );

  return {
    ...snapshot,
    start,
    end,
    toggleMicrophoneMute,
    enableAudio,
    clearTranscript,
  };
}
