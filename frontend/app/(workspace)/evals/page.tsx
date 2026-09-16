import type { Metadata } from "next";

import { EvalsRoute } from "./route-client";

export const metadata: Metadata = { title: "Evaluations" };

export default function Page() {
  return <EvalsRoute />;
}
