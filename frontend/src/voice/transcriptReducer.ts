import type { VoiceTranscriptEntry } from './types';

export const DEFAULT_TRANSCRIPT_LIMIT = 100;

export function upsertTranscriptEntry(
  entries: readonly VoiceTranscriptEntry[],
  incoming: VoiceTranscriptEntry,
  limit = DEFAULT_TRANSCRIPT_LIMIT,
): readonly VoiceTranscriptEntry[] {
  const text = incoming.text.trim();

  if (text.length === 0 || limit < 1) {
    return entries;
  }

  const nextEntry = { ...incoming, text };
  const existingIndex = entries.findIndex((entry) => entry.id === incoming.id);

  if (existingIndex === -1) {
    return [...entries, nextEntry].slice(-limit);
  }

  const existing = entries[existingIndex];

  // A late interim stream must never roll a finalized segment backwards.
  if (existing.final && !nextEntry.final) {
    return entries;
  }

  if (
    existing.text === nextEntry.text &&
    existing.final === nextEntry.final
  ) {
    return entries;
  }

  const next = [...entries];
  next[existingIndex] = {
    ...nextEntry,
    timestamp: existing.timestamp,
  };
  return next;
}
