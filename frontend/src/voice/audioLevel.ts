import { createAudioAnalyser, type RemoteAudioTrack } from 'livekit-client';

export interface RemoteAudioLevelMonitorOptions {
  intervalMs?: number;
  minimumDelta?: number;
  onAmplitude: (amplitude: number) => void;
}

export class RemoteAudioLevelMonitor {
  private readonly intervalId: ReturnType<typeof setInterval>;
  private readonly cleanupAnalyser: () => Promise<void>;
  private readonly onAmplitude: (amplitude: number) => void;
  private readonly minimumDelta: number;
  private lastAmplitude = 0;
  private stopped = false;

  constructor(
    track: RemoteAudioTrack,
    {
      intervalMs = 80,
      minimumDelta = 0.025,
      onAmplitude,
    }: RemoteAudioLevelMonitorOptions,
  ) {
    const { calculateVolume, cleanup } = createAudioAnalyser(track, {
      fftSize: 256,
      minDecibels: -70,
      maxDecibels: -10,
      smoothingTimeConstant: 0.72,
    });

    this.cleanupAnalyser = cleanup;
    this.onAmplitude = onAmplitude;
    this.minimumDelta = minimumDelta;

    this.intervalId = setInterval(() => {
      const amplitude = Math.min(1, Math.max(0, calculateVolume()));

      if (
        Math.abs(amplitude - this.lastAmplitude) >= this.minimumDelta ||
        (amplitude === 0 && this.lastAmplitude !== 0)
      ) {
        this.lastAmplitude = amplitude;
        this.onAmplitude(amplitude);
      }
    }, intervalMs);
  }

  stop(): void {
    if (this.stopped) {
      return;
    }

    this.stopped = true;
    clearInterval(this.intervalId);
    this.onAmplitude(0);
    void this.cleanupAnalyser().catch(() => undefined);
  }
}
