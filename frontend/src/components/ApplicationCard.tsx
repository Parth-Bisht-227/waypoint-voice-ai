import {
  applicationStatusLabels,
  formatDocumentCode,
  formatTravelDate,
} from '../domain/application';
import type { ApplicationResourceState } from '../hooks/useApplication';

export interface ApplicationCardProps {
  resource: ApplicationResourceState;
  onRetry: () => void;
}

function CalendarIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M7 2v3M17 2v3M3.5 8.5h17M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2Z" />
      <path d="M7 12h2M11 12h2M15 12h2M7 16h2M11 16h2" />
    </svg>
  );
}

function DocumentIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 2.5h8l4 4V21H6zM14 2.5V7h4M9 12h6M9 16h6" />
    </svg>
  );
}

function RetryButton({ onRetry }: Pick<ApplicationCardProps, 'onRetry'>) {
  return (
    <button
      className="application-card__retry"
      type="button"
      onClick={onRetry}
    >
      Try again
    </button>
  );
}

export function ApplicationCard({
  resource,
  onRetry,
}: ApplicationCardProps) {
  const application = resource.status === 'ready' ? resource.application : null;
  const stateClass = resource.status.replace('_', '-');

  return (
    <aside
      className={'application-card application-card--' + stateClass}
      aria-busy={resource.status === 'loading'}
      aria-labelledby="application-card-title"
      data-resource-state={resource.status}
    >
      <div className="application-card__topline">
        <p id="application-card-title">Current application</p>
        {application ? <span>Live record</span> : null}
      </div>

      {application ? (
        <>
          <div className="application-card__identity">
            <span className="application-card__id">
              {application.applicationId}
            </span>
            <span
              className={'status-chip status-chip--' + application.status}
            >
              {applicationStatusLabels[application.status]}
            </span>
          </div>

          <dl className="application-card__details">
            <div className="application-card__destination">
              <dt>Destination</dt>
              <dd>
                <span aria-hidden="true">↗</span>
                {application.destination}
              </dd>
            </div>

            <div>
              <dt>
                <CalendarIcon />
                Travel date
              </dt>
              <dd>{formatTravelDate(application.travelDate)}</dd>
            </div>

            <div>
              <dt>
                <DocumentIcon />
                Missing documents
              </dt>
              <dd>
                {application.missingDocuments.length > 0
                  ? application.missingDocuments
                      .map(formatDocumentCode)
                      .join(', ')
                  : 'None'}
              </dd>
            </div>
          </dl>
        </>
      ) : (
        <div
          className="application-card__resource-state"
          role={resource.status === 'error' ? 'alert' : 'status'}
        >
          <div className="application-card__identity">
            <span className="application-card__id">
              {resource.applicationId}
            </span>
            <span className={'status-chip status-chip--' + stateClass}>
              {resource.status === 'loading'
                ? 'Loading'
                : resource.status === 'not_found'
                  ? 'Not found'
                  : 'Unavailable'}
            </span>
          </div>

          <div className="application-card__message">
            <p>
              {resource.status === 'loading'
                ? 'Loading the application record…'
                : resource.status === 'not_found'
                  ? 'No application record was found for ' +
                    resource.applicationId +
                    '.'
                  : resource.status === 'error'
                    ? resource.message
                    : ''}
            </p>
            {resource.status === 'not_found' || resource.status === 'error' ? (
              <RetryButton onRetry={onRetry} />
            ) : null}
          </div>
        </div>
      )}
    </aside>
  );
}
