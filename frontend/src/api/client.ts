export type ApiRequestErrorKind =
  | 'network'
  | 'http'
  | 'invalid_response';

export class ApiRequestError extends Error {
  readonly kind: ApiRequestErrorKind;
  readonly status: number | null;
  readonly originalError?: unknown;

  constructor(
    kind: ApiRequestErrorKind,
    message: string,
    options: {
      status?: number;
      originalError?: unknown;
    } = {},
  ) {
    super(message);
    this.name = 'ApiRequestError';
    this.kind = kind;
    this.status = options.status ?? null;
    this.originalError = options.originalError;
  }
}

export function isAbortError(error: unknown): boolean {
  return (
    typeof error === 'object' &&
    error !== null &&
    'name' in error &&
    error.name === 'AbortError'
  );
}

function responseDetail(value: unknown): string | undefined {
  if (
    typeof value === 'object' &&
    value !== null &&
    'detail' in value &&
    typeof value.detail === 'string'
  ) {
    return value.detail;
  }

  return undefined;
}

export async function requestJson<T>(
  path: string,
  parse: (value: unknown) => T,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set('Accept', 'application/json');

  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }

    throw new ApiRequestError(
      'network',
      'The Waypoint service could not be reached',
      { originalError: error },
    );
  }

  let rawBody: string;
  try {
    rawBody = await response.text();
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }

    throw new ApiRequestError(
      'network',
      'The Waypoint response could not be read',
      { status: response.status, originalError: error },
    );
  }

  let body: unknown;
  try {
    body = rawBody.length > 0 ? JSON.parse(rawBody) : null;
  } catch (error) {
    if (!response.ok) {
      throw new ApiRequestError(
        'http',
        `Waypoint returned HTTP ${response.status}`,
        { status: response.status, originalError: error },
      );
    }

    throw new ApiRequestError(
      'invalid_response',
      'Waypoint returned malformed JSON',
      { status: response.status, originalError: error },
    );
  }

  if (!response.ok) {
    throw new ApiRequestError(
      'http',
      responseDetail(body) ?? `Waypoint returned HTTP ${response.status}`,
      { status: response.status },
    );
  }

  try {
    return parse(body);
  } catch (error) {
    throw new ApiRequestError(
      'invalid_response',
      'Waypoint returned data in an unexpected format',
      { status: response.status, originalError: error },
    );
  }
}
