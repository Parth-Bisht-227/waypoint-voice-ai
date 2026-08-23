import type { ApplicationSignal } from './types';

const MAX_APPLICATION_EVENT_BYTES = 4_096;
const APPLICATION_ID_PATTERN = /^APP[A-Z0-9_-]{1,60}$/;
const signalTypes = new Set([
  'application_context',
  'application_updated',
] as const);

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isValidApplicationId(value: string): boolean {
  return APPLICATION_ID_PATTERN.test(value);
}

export function parseApplicationSignal(
  payload: Uint8Array,
): ApplicationSignal | null {
  if (payload.byteLength === 0 || payload.byteLength > MAX_APPLICATION_EVENT_BYTES) {
    return null;
  }

  try {
    const decoded = new TextDecoder('utf-8', { fatal: true }).decode(payload);
    const parsed: unknown = JSON.parse(decoded);

    if (!isRecord(parsed)) {
      return null;
    }

    const keys = Object.keys(parsed);
    if (
      keys.length !== 2 ||
      !keys.includes('type') ||
      !keys.includes('application_id')
    ) {
      return null;
    }

    const type = parsed.type;
    const applicationId = parsed.application_id;

    if (
      typeof type !== 'string' ||
      !signalTypes.has(type as 'application_context' | 'application_updated') ||
      typeof applicationId !== 'string' ||
      !isValidApplicationId(applicationId)
    ) {
      return null;
    }

    return {
      type: type as ApplicationSignal['type'],
      applicationId,
    };
  } catch {
    return null;
  }
}
