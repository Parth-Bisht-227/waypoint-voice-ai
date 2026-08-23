import { parseApplicationId } from '../domain/application';

const configuredApplicationId =
  import.meta.env.VITE_DEFAULT_APPLICATION_ID?.trim() || 'APP001';

export const DEFAULT_APPLICATION_ID = parseApplicationId(
  configuredApplicationId,
  'VITE_DEFAULT_APPLICATION_ID',
);

export const apiPaths = {
  application(applicationId: string): string {
    return `/api/applications/${encodeURIComponent(
      parseApplicationId(applicationId),
    )}`;
  },
  missingDocuments(applicationId: string): string {
    return `${apiPaths.application(applicationId)}/missing-documents`;
  },
  voiceToken: '/api/voice/token',
} as const;
