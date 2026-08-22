import type {
  ApplicationSnapshot,
  ApplicationSnapshotAdapter,
  ApplicationWireRecord,
  MissingDocumentsWireRecord,
} from '../domain/application';

const mockApplicationRecord = {
  application_id: 'APP001',
  destination: 'Solara',
  status: 'blocked',
  travel_date: '2026-09-10',
} satisfies ApplicationWireRecord;

const mockMissingDocumentsRecord = {
  application_id: 'APP001',
  missing_documents: ['bank_statement'],
} satisfies MissingDocumentsWireRecord;

function adaptApplicationRecords(
  application: ApplicationWireRecord,
  documents: MissingDocumentsWireRecord,
): ApplicationSnapshot {
  if (application.application_id !== documents.application_id) {
    throw new Error('Mock application records reference different application IDs.');
  }

  return {
    applicationId: application.application_id,
    destination: application.destination,
    status: application.status,
    travelDate: application.travel_date,
    missingDocuments: [...documents.missing_documents],
  };
}

export const mockApplicationAdapter: ApplicationSnapshotAdapter = {
  getSnapshot() {
    return adaptApplicationRecords(
      mockApplicationRecord,
      mockMissingDocumentsRecord,
    );
  },
};

