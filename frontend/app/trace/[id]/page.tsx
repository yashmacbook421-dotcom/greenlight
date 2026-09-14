import type { Metadata } from "next";

import { TraceRoute } from "./route-client";

export const metadata: Metadata = { title: "Agent Trace" };

export default async function Page({ params }: PageProps<"/trace/[id]">) {
  const { id } = await params;
  return <TraceRoute id={id} />;
}
