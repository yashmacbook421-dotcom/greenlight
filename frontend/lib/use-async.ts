"use client";

import { useEffect, useState } from "react";

export type AsyncState<T> =
  | { status: "loading" }
  | { status: "error"; error: Error; retry: () => void }
  | { status: "ready"; data: T; reload: () => void };

type Result<T> = { key: string; data?: T; error?: Error };

/** Client-side replacement for the preview's route loaders. `key` identifies what is being loaded. */
export function useAsync<T>(load: () => Promise<T>, key: string): AsyncState<T> {
  const [attempt, setAttempt] = useState(0);
  const [result, setResult] = useState<Result<T> | null>(null);
  const token = `${key}#${attempt}`;

  useEffect(() => {
    let cancelled = false;
    load().then(
      (data) => !cancelled && setResult({ key: token, data }),
      (error: Error) => !cancelled && setResult({ key: token, error }),
    );
    return () => {
      cancelled = true;
    };
    // `load` is recreated every render; `token` captures what it loads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  const again = () => setAttempt((n) => n + 1);
  if (!result || result.key !== token) return { status: "loading" };
  if (result.error) return { status: "error", error: result.error, retry: again };
  return { status: "ready", data: result.data as T, reload: again };
}
