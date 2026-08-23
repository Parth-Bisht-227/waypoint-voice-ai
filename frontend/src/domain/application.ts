export const applicationStatuses = [
  'processing',
  'approved',
  'blocked',
  'action_required',
] as const;

export type ApplicationStatus = (typeof applicationStatuses)[number];

export interface ApplicationSnapshot {
  applicationId: string;
  destination: string;
  status: ApplicationStatus;
  travelDate: string;
  missingDocuments: readonly string[];
}

export interface ApplicationWireRecord {
  application_id: string;
  destination: string;
  status: ApplicationStatus;
  travel_date: string;
}

export interface MissingDocumentsWireRecord {
  application_id: string;
  missing_documents: readonly string[];
}

export interface ApplicationSnapshotAdapter {
  getSnapshot(): ApplicationSnapshot;
}
export class ApplicationPayloadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ApplicationPayloadError';
  }
}

export const applicationStatusLabels: Record<ApplicationStatus, string> = {
  processing: 'Processing',
  approved: 'Approved',
  blocked: 'Blocked',
  action_required: 'Action required',
};
const applicationIdPattern = /^[A-Z0-9][A-Z0-9_-]{0,63}$/;
const isoDatePattern = /^\d{4}-\d{2}-\d{2}$/;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

function readNonEmptyString(
  record: Record<string, unknown>,
  key: string,
  payloadName: string,
): string {
  const value = record[key];

  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new ApplicationPayloadError(
      `${payloadName}.${key} must be a non-empty string`,
    );
  }

  return value.trim();
}

function isApplicationStatus(value: unknown): value is ApplicationStatus {
  return (
    typeof value === 'string' &&
    applicationStatuses.includes(value as ApplicationStatus)
  );
}

function isRealIsoDate(value: string): boolean {
  if (!isoDatePattern.test(value)) {
    return false;
  }

  const [year, month, day] = value.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));

  return (
    date.getUTCFullYear() === year &&
    date.getUTCMonth() === month - 1 &&
    date.getUTCDate() === day
  );
}

export function parseApplicationId(
  value: unknown,
  label = 'Application ID',
): string {
  if (typeof value !== 'string') {
    throw new ApplicationPayloadError(`${label} must be a string`);
  }

  const applicationId = value.trim().toUpperCase();
  if (!applicationIdPattern.test(applicationId)) {
    throw new ApplicationPayloadError(`${label} has an invalid format`);
  }

  return applicationId;
}

export function parseApplicationWireRecord(
  value: unknown,
): ApplicationWireRecord {
  if (!isRecord(value)) {
    throw new ApplicationPayloadError('Application response must be an object');
  }

  const status = value.status;
  if (!isApplicationStatus(status)) {
    throw new ApplicationPayloadError(
      `Application response has an unsupported status: ${String(status)}`,
    );
  }

  const travelDate = readNonEmptyString(
    value,
    'travel_date',
    'Application response',
  );
  if (!isRealIsoDate(travelDate)) {
    throw new ApplicationPayloadError(
      'Application response.travel_date must be a real date using YYYY-MM-DD',
    );
  }

  return {
    application_id: parseApplicationId(
      value.application_id,
      'Application response.application_id',
    ),
    destination: readNonEmptyString(
      value,
      'destination',
      'Application response',
    ),
    status,
    travel_date: travelDate,
  };
}

export function parseMissingDocumentsWireRecord(
  value: unknown,
): MissingDocumentsWireRecord {
  if (!isRecord(value)) {
    throw new ApplicationPayloadError(
      'Missing-documents response must be an object',
    );
  }

  const missingDocuments = value.missing_documents;
  if (
    !Array.isArray(missingDocuments) ||
    !missingDocuments.every(
      (documentCode) =>
        typeof documentCode === 'string' && documentCode.trim().length > 0,
    )
  ) {
    throw new ApplicationPayloadError(
      'Missing-documents response must contain an array of document codes',
    );
  }

  return {
    application_id: parseApplicationId(
      value.application_id,
      'Missing-documents response.application_id',
    ),
    missing_documents: missingDocuments.map((documentCode) =>
      documentCode.trim(),
    ),
  };
}

export function adaptApplicationRecords(
  applicationValue: unknown,
  missingDocumentsValue: unknown,
): ApplicationSnapshot {
  const application = parseApplicationWireRecord(applicationValue);
  const missingDocuments = parseMissingDocumentsWireRecord(
    missingDocumentsValue,
  );

  if (application.application_id !== missingDocuments.application_id) {
    throw new ApplicationPayloadError(
      'Application and missing-documents responses refer to different applications',
    );
  }

  return {
    applicationId: application.application_id,
    destination: application.destination,
    status: application.status,
    travelDate: application.travel_date,
    missingDocuments: missingDocuments.missing_documents,
  };
}

export function formatDocumentCode(documentCode: string): string {
  return documentCode
    .split('_')
    .filter(Boolean)
    .map((word) => word[0]?.toUpperCase() + word.slice(1))
    .join(' ');
}

export function formatTravelDate(isoDate: string): string {
  const [year, month, day] = isoDate.split('-').map(Number);

  if (!year || !month || !day) {
    return isoDate;
  }

  return new Intl.DateTimeFormat('en', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

