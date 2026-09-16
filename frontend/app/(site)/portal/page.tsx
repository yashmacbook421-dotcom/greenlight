import type { Metadata } from "next";

import { PortalHomeRoute } from "./route-client";

export const metadata: Metadata = { title: "My applications" };

export default function Page() {
  return <PortalHomeRoute />;
}
