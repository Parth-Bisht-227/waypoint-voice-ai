import { apiPaths } from './config';
import { requestJson } from './client';

export interface VoiceTokenResponse {
  server_url: string;
  participant_token: string;
  room_name?: string;
  participant_identity?: string;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function requiredString(value: unknown, fieldName: string): string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new Error(`${fieldName} must be a non-empty string`);
  }

  return value.trim();
}

function optionalString(
  value: unknown,
  fieldName: string,
): string | undefined {
  if (value === undefined) {
    return undefined;
  }

  return requiredString(value, fieldName);
}

export function parseVoiceTokenResponse(
  value: unknown,
): VoiceTokenResponse {
  if (!isRecord(value)) {
    throw new Error('Voice-token response must be an object');
  }

  const serverUrl = requiredString(value.server_url, 'server_url');
  let parsedUrl: URL;
  try {
    parsedUrl = new URL(serverUrl);
  } catch {
    throw new Error('server_url must be a valid URL');
  }

  if (parsedUrl.protocol !== 'wss:' && parsedUrl.protocol !== 'ws:') {
    throw new Error('server_url must use ws or wss');
  }

  return {
    server_url: serverUrl,
    participant_token: requiredString(
      value.participant_token,
      'participant_token',
    ),
    room_name: optionalString(value.room_name, 'room_name'),
    participant_identity: optionalString(
      value.participant_identity,
      'participant_identity',
    ),
  };
}

export function requestVoiceToken(
  signal?: AbortSignal,
): Promise<VoiceTokenResponse> {
  return requestJson(apiPaths.voiceToken, parseVoiceTokenResponse, {
    method: 'POST',
    cache: 'no-store',
    signal,
  });
}
