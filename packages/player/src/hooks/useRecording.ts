import { useState, useEffect } from 'react';
import type { RecordingLog } from '../types/recording';

export interface UseRecordingOptions {
  data?: RecordingLog;
  src?: string;
}

export interface UseRecordingResult {
  recording: RecordingLog | null;
  loading: boolean;
  error: Error | null;
}

/**
 * Hook to load recording data from either inline data or URL.
 */
export function useRecording({ data, src }: UseRecordingOptions): UseRecordingResult {
  const [recording, setRecording] = useState<RecordingLog | null>(data ?? null);
  const [loading, setLoading] = useState(!!src && !data);
  const [error, setError] = useState<Error | null>(null);

  // Handle inline data changes
  useEffect(() => {
    if (data) {
      setRecording(data);
      setLoading(false);
      setError(null);
    }
  }, [data]);

  // Fetch from URL if src provided
  useEffect(() => {
    if (!src || data) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    fetch(src)
      .then((response) => {
        if (!response.ok) {
          throw new Error(`Failed to fetch recording: ${response.status} ${response.statusText}`);
        }
        return response.json();
      })
      .then((json: RecordingLog) => {
        if (!cancelled) {
          setRecording(json);
          setLoading(false);
        }
      })
      .catch((err: Error) => {
        if (!cancelled) {
          setError(err);
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [src, data]);

  return { recording, loading, error };
}
