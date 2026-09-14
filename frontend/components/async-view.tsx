"use client";

import type { ReactNode } from "react";

import type { AsyncState } from "@/lib/use-async";
import { Button, Panel } from "./ui";

export function AsyncView<T>({ state, children }: { state: AsyncState<T>; children: (data: T) => ReactNode }) {
  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-live="polite">
        <div className="h-8 w-64 animate-pulse rounded-md bg-muted" />
        <div className="h-40 animate-pulse rounded-lg bg-muted" />
        <div className="h-64 animate-pulse rounded-lg bg-muted" />
      </div>
    );
  }
  if (state.status === "error") {
    return (
      <Panel title="This page didn't load">
        <div className="space-y-3 p-4 text-sm">
          <p>
            Could not reach the Greenlight API: <strong>{state.error.message}</strong>
          </p>
          <p className="text-muted-foreground">
            Check that the backend is running (<code>docker compose up -d</code>) and try again.
          </p>
          <Button onClick={state.retry}>Try again</Button>
        </div>
      </Panel>
    );
  }
  return <>{children(state.data)}</>;
}
