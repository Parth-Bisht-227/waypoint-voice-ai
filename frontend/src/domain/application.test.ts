import { describe, expect, it } from 'vitest';
import {
  adaptApplicationRecords,
  parseApplicationId,
  parseApplicationWireRecord,
} from './application';

describe('application payload boundary', () => {
  it('normalizes configured application IDs', () => {
    expect(parseApplicationId(' app001 ')).toBe('APP001');
  });

  it('adapts matching authoritative records', () => {
    expect(
      adaptApplicationRecords(
        {
          application_id: 'APP001',
          destination: 'Solara',
          status: 'blocked',
          travel_date: '2026-09-10',
        },
        {
          application_id: 'APP001',
          missing_documents: ['bank_statement'],
        },
      ),
    ).toEqual({
      applicationId: 'APP001',
      destination: 'Solara',
      status: 'blocked',
      travelDate: '2026-09-10',
      missingDocuments: ['bank_statement'],
    });
  });

  it('rejects mismatched application records', () => {
    expect(() =>
      adaptApplicationRecords(
        {
          application_id: 'APP001',
          destination: 'Solara',
          status: 'processing',
          travel_date: '2026-09-10',
        },
        {
          application_id: 'APP004',
          missing_documents: [],
        },
      ),
    ).toThrow(/different applications/i);
  });

  it('rejects impossible dates and unsupported statuses', () => {
    expect(() =>
      parseApplicationWireRecord({
        application_id: 'APP001',
        destination: 'Solara',
        status: 'complete',
        travel_date: '2026-09-10',
      }),
    ).toThrow(/unsupported status/i);

    expect(() =>
      parseApplicationWireRecord({
        application_id: 'APP001',
        destination: 'Solara',
        status: 'processing',
        travel_date: '2026-02-31',
      }),
    ).toThrow(/real date/i);
  });
});
