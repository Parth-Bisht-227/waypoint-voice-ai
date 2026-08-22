export type TranscriptSpeaker = 'user' | 'assistant';

export interface TranscriptEntry {
  id: string;
  speaker: TranscriptSpeaker;
  timestamp: string;
  text: string;
}

export const mockTranscript: readonly TranscriptEntry[] = [
  {
    id: 'turn-01',
    speaker: 'user',
    timestamp: '09:41',
    text: 'Hi, can you check my travel application?',
  },
  {
    id: 'turn-02',
    speaker: 'assistant',
    timestamp: '09:41',
    text: 'I can help with that. What is your application ID?',
  },
  {
    id: 'turn-03',
    speaker: 'user',
    timestamp: '09:42',
    text: 'It is APP zero zero one.',
  },
  {
    id: 'turn-04',
    speaker: 'assistant',
    timestamp: '09:42',
    text: 'I found it. Your Solara application is blocked because a bank statement is still missing.',
  },
];

