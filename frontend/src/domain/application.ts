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

export const applicationStatusLabels: Record<ApplicationStatus, string> = {
  processing: 'Processing',
  approved: 'Approved',
  blocked: 'Blocked',
  action_required: 'Action required',
};

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

