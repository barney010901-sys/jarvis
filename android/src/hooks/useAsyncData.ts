import { useCallback, useEffect, useState } from 'react';

/**
 * Small shared data-fetching hook — every Phase 3 screen (dashboard,
 * wallet, business, memory search, approvals, audit, projects, contacts,
 * capabilities) follows the same fetch/loading/error/refresh shape, so
 * it's centralized here instead of five near-identical copies.
 */
export function useAsyncData<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => refresh(), [refresh]);

  return { data, loading, error, refresh };
}
