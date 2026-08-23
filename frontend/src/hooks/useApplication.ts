import { useCallback, useEffect, useRef, useState } from 'react';
import { getApplicationSnapshot } from '../api/applications';
import {
  ApiRequestError,
  isAbortError,
} from '../api/client';
import { DEFAULT_APPLICATION_ID } from '../api/config';
import {
  parseApplicationId,
  type ApplicationSnapshot,
} from '../domain/application';

export type ApplicationResourceState =
  | {
      status: 'loading';
      applicationId: string;
    }
  | {
      status: 'ready';
      applicationId: string;
      application: ApplicationSnapshot;
    }
  | {
      status: 'not_found';
      applicationId: string;
    }
  | {
      status: 'error';
      applicationId: string;
      message: string;
    };

export interface UseApplicationResult {
  state: ApplicationResourceState;
  refetch: () => void;
}

function applicationErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) {
    if (error.kind === 'network') {
      return 'The application service is currently unreachable.';
    }

    if (error.kind === 'invalid_response') {
      return 'The application service returned an unexpected response.';
    }

    if (error.status !== null && error.status >= 500) {
      return 'The application service is temporarily unavailable.';
    }
  }

  return 'Application information could not be loaded.';
}

export function useApplication(
  applicationId = DEFAULT_APPLICATION_ID,
): UseApplicationResult {
  const requestedApplicationId = parseApplicationId(applicationId);
  const requestVersion = useRef(0);
  const [refreshVersion, setRefreshVersion] = useState(0);
  const [state, setState] = useState<ApplicationResourceState>({
    status: 'loading',
    applicationId: requestedApplicationId,
  });

  useEffect(() => {
    const version = ++requestVersion.current;
    const controller = new AbortController();

    setState({
      status: 'loading',
      applicationId: requestedApplicationId,
    });

    void getApplicationSnapshot(
      requestedApplicationId,
      controller.signal,
    )
      .then((application) => {
        if (
          !controller.signal.aborted &&
          requestVersion.current === version
        ) {
          setState({
            status: 'ready',
            applicationId: requestedApplicationId,
            application,
          });
        }
      })
      .catch((error: unknown) => {
        if (
          controller.signal.aborted ||
          requestVersion.current !== version ||
          isAbortError(error)
        ) {
          return;
        }

        if (error instanceof ApiRequestError && error.status === 404) {
          setState({
            status: 'not_found',
            applicationId: requestedApplicationId,
          });
          return;
        }

        setState({
          status: 'error',
          applicationId: requestedApplicationId,
          message: applicationErrorMessage(error),
        });
      });

    return () => {
      controller.abort();
    };
  }, [refreshVersion, requestedApplicationId]);

  const refetch = useCallback(() => {
    setRefreshVersion((version) => version + 1);
  }, []);

  const visibleState =
    state.applicationId === requestedApplicationId
      ? state
      : {
          status: 'loading' as const,
          applicationId: requestedApplicationId,
        };

  return { state: visibleState, refetch };
}
