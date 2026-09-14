"use client";

import { listEvals } from "@/lib/api";
import { useAsync } from "@/lib/use-async";
import { AboutPage } from "@/views/about-view";

export function AboutRoute() {
  const state = useAsync(listEvals, "evals");
  // The explanation must render even if eval data is unavailable.
  return <AboutPage runs={state.status === "ready" ? state.data : []} />;
}
