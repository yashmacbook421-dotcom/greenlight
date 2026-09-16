import type { Metadata } from "next";

import { QueueRoute } from "./route-client";

export const metadata: Metadata = { title: "Review Queue" };

export default function Page() {
  return <QueueRoute />;
}
