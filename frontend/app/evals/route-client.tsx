"use client";

import { useEffect, useState } from "react";

import { AsyncView } from "@/components/async-view";
import { Panel } from "@/components/ui";
import { getEval, listEvals } from "@/lib/api";
import type { EvalDetail, EvalRun } from "@/lib/types";
import { useAsync } from "@/lib/use-async";
import { EvalsPage } from "@/views/evals-view";

export function EvalsRoute() {
  const state = useAsync(listEvals, "evals");
  return (
    <AsyncView state={state}>
      {(runs) =>
        runs.length ? (
          <EvalsWithSelection runs={runs} />
        ) : (
          <Panel title="No evaluation runs yet">
            <p className="p-4 text-sm text-muted-foreground">
              Run <code>python -m scripts.run_eval --mode oracle</code> in the backend to create one.
            </p>
          </Panel>
        )
      }
    </AsyncView>
  );
}

function EvalsWithSelection({ runs }: { runs: EvalRun[] }) {
  const initial =
    runs.find((r) => r.mode === "live" && r.status === "completed") ??
    runs.find((r) => r.status === "completed") ??
    runs[0];
  const [selectedId, setSelectedId] = useState(initial.id);
  const [loaded, setLoaded] = useState<{ id: string; detail?: EvalDetail; error?: string } | null>(null);

  useEffect(() => {
    let cancelled = false;
    getEval(selectedId).then(
      (detail) => !cancelled && setLoaded({ id: selectedId, detail }),
      (e: Error) => !cancelled && setLoaded({ id: selectedId, error: `Could not load this run: ${e.message}` }),
    );
    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  const current = loaded?.id === selectedId ? loaded : null;
  return (
    <EvalsPage
      runs={runs}
      selectedId={selectedId}
      details={current?.detail ?? null}
      loadingDetail={current === null}
      detailError={current?.error ?? ""}
      onSelect={setSelectedId}
    />
  );
}
