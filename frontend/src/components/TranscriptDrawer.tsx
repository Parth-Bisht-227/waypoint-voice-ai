import type { TranscriptEntry } from '../data/mockTranscript';

interface TranscriptDrawerProps {
  entries: readonly TranscriptEntry[];
}

export function TranscriptDrawer({ entries }: TranscriptDrawerProps) {
  return (
    <details className="transcript-drawer">
      <summary>
        <span className="transcript-drawer__summary-icon" aria-hidden="true">
          ↑
        </span>
        <span>Transcript</span>
        <span className="transcript-drawer__count">{entries.length} turns</span>
      </summary>

      <div className="transcript-drawer__panel">
        <div className="transcript-drawer__heading">
          <div>
            <p>Call transcript</p>
            <span>Mock conversation · not saved</span>
          </div>
          <span aria-hidden="true">Live notes / 001</span>
        </div>

        <ol className="transcript-list">
          {entries.map((entry) => (
            <li
              className={`transcript-entry transcript-entry--${entry.speaker}`}
              key={entry.id}
            >
              <div className="transcript-entry__meta">
                <span>{entry.speaker === 'user' ? 'You' : 'Waypoint'}</span>
                <time>{entry.timestamp}</time>
              </div>
              <p>{entry.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </details>
  );
}

