"use client";

import { AsyncView } from "@/components/async-view";
import { listCases, listFamilies } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { QueuePage } from "@/views/queue-view";

export function QueueRoute() {
  const state = useAsync(async () => ({ cases: await listCases(), families: await listFamilies() }), "queue");
  return <AsyncView state={state}>{(d) => <QueuePage initial={d.cases} families={d.families} />}</AsyncView>;
}
