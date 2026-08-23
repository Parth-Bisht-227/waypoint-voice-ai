import { describe, expect, it } from 'vitest';
import { parseVoiceTokenResponse } from './voiceToken';

describe('voice token response boundary', () => {
  it('accepts the standardized participant token contract', () => {
    expect(
      parseVoiceTokenResponse({
        server_url: 'wss://waypoint.livekit.cloud',
        participant_token: 'short-lived-token',
        room_name: 'waypoint-001',
        participant_identity: 'browser-001',
      }),
    ).toEqual({
      server_url: 'wss://waypoint.livekit.cloud',
      participant_token: 'short-lived-token',
      room_name: 'waypoint-001',
      participant_identity: 'browser-001',
    });
  });

  it('rejects the legacy token field and non-WebSocket URLs', () => {
    expect(() =>
      parseVoiceTokenResponse({
        server_url: 'wss://waypoint.livekit.cloud',
        token: 'legacy-field',
      }),
    ).toThrow(/participant_token/i);

    expect(() =>
      parseVoiceTokenResponse({
        server_url: 'https://waypoint.livekit.cloud',
        participant_token: 'short-lived-token',
      }),
    ).toThrow(/ws or wss/i);
  });
});
