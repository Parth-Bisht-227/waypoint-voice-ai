import type { VoiceTranscriptEntry } from '../voice';

export interface TranscriptDrawerProps {
  entries: readonly VoiceTranscriptEntry[];
}

interface FormattedTranscriptTime {
  label: string;
  dateTime?: string;
}

const transcriptTimeFormatter = new Intl.DateTimeFormat(undefined, {
  hour: '2-digit',
  minute: '2-digit',
});

function transcriptTime(timestamp: number): FormattedTranscriptTime {
  const date = new Date(timestamp);

  if (Number.isNaN(date.getTime())) {
    return { label: 'Time unavailable' };
  }

  return {
    label: transcriptTimeFormatter.format(date),
    dateTime: date.toISOString(),
  };
}

export function TranscriptDrawer({ entries }: TranscriptDrawerProps) {
  const turnLabel =
    entries.length === 0
      ? 'No turns'
      : entries.length +
        ' ' +
        (entries.length === 1 ? 'turn' : 'turns');

  return (
    <details className="transcript-drawer">
      <summary>
        <span className="transcript-drawer__summary-icon" aria-hidden="true">
          ↑
        </span>
        <span>Transcript</span>
        <span className="transcript-drawer__count">{turnLabel}</span>
      </summary>

      <div className="transcript-drawer__panel">
        <div className="transcript-drawer__heading">
          <div>
            <p>Call transcript</p>
            <span>Live session / not saved</span>
          </div>
          <span aria-hidden="true">Live transcript</span>
        </div>

        {entries.length === 0 ? (
          <p className="transcript-drawer__empty" role="status">
            No transcript yet. Utterances will appear here during the voice
            session.
          </p>
        ) : (
          <ol className="transcript-list" aria-label="Voice transcript">
            {entries.map((entry) => {
              const time = transcriptTime(entry.timestamp);

              return (
                <li
                  className={
                    'transcript-entry transcript-entry--' +
                    entry.role +
                    ' transcript-entry--' +
                    (entry.final ? 'final' : 'interim')
                  }
                  key={entry.id}
                >
                  <div className="transcript-entry__meta">
                    <span>{entry.role === 'user' ? 'You' : 'Waypoint'}</span>
                    <span className="transcript-entry__state">
                      {entry.final ? 'Final' : 'Interim'}
                    </span>
                    <time dateTime={time.dateTime}>{time.label}</time>
                  </div>
                  <p>{entry.text}</p>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </details>
  );
}
