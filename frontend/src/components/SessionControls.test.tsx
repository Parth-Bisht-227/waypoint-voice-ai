import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { SessionControls } from './SessionControls';

const handlers = {
  onStart: () => undefined,
  onEnd: () => undefined,
  onToggleMicrophoneMute: () => undefined,
  onEnableAudio: () => undefined,
};

describe('SessionControls', () => {
  it('renders an accessible mute toggle only for a connected call', () => {
    const markup = renderToStaticMarkup(
      <SessionControls
        state="listening"
        transportState="connected"
        isMicrophoneMuted={false}
        canPlaybackAudio
        {...handlers}
      />,
    );

    expect(markup).toContain('session-control--mute');
    expect(markup).toContain('aria-pressed="false"');
    expect(markup).toContain('<span>Mute</span>');
    expect(markup).toContain('<span>End call</span>');

    const disconnectedMarkup = renderToStaticMarkup(
      <SessionControls
        state="idle"
        transportState="disconnected"
        isMicrophoneMuted={false}
        canPlaybackAudio
        {...handlers}
      />,
    );

    expect(disconnectedMarkup).not.toContain('session-control--mute');
  });

  it('shows the unmute action and pressed state while muted', () => {
    const markup = renderToStaticMarkup(
      <SessionControls
        state="reconnecting"
        transportState="reconnecting"
        isMicrophoneMuted
        canPlaybackAudio
        {...handlers}
      />,
    );

    expect(markup).toContain('aria-pressed="true"');
    expect(markup).toContain('<span>Unmute</span>');
  });
});
