"use client";

import { AsyncView } from "@/components/async-view";
import { getTrace } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { TracePage } from "@/views/trace-view";

export function TraceRoute({ id }: { id: string }) {
  const state = useAsync(() => getTrace(id), id);
  return <AsyncView state={state}>{(runs) => <TracePage runs={runs} caseId={id} />}</AsyncView>;
}
