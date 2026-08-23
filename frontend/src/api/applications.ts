import {
  adaptApplicationRecords,
  type ApplicationSnapshot,
  parseApplicationId,
  parseApplicationWireRecord,
  parseMissingDocumentsWireRecord,
} from '../domain/application';
import { apiPaths } from './config';
import { requestJson } from './client';

export async function getApplication(
  applicationId: string,
  signal?: AbortSignal,
) {
  const normalizedId = parseApplicationId(applicationId);

  return requestJson(
    apiPaths.application(normalizedId),
    parseApplicationWireRecord,
    { signal },
  );
}

export async function getMissingDocuments(
  applicationId: string,
  signal?: AbortSignal,
) {
  const normalizedId = parseApplicationId(applicationId);

  return requestJson(
    apiPaths.missingDocuments(normalizedId),
    parseMissingDocumentsWireRecord,
    { signal },
  );
}

export async function getApplicationSnapshot(
  applicationId: string,
  signal?: AbortSignal,
): Promise<ApplicationSnapshot> {
  const normalizedId = parseApplicationId(applicationId);
  const [application, missingDocuments] = await Promise.all([
    getApplication(normalizedId, signal),
    getMissingDocuments(normalizedId, signal),
  ]);

  const snapshot = adaptApplicationRecords(application, missingDocuments);
  if (snapshot.applicationId !== normalizedId) {
    throw new Error(
      'The application response did not match the requested application ID',
    );
  }

  return snapshot;
}
