import type { Metadata } from "next";

import { PortalNewPage } from "@/views/portal-new-view";

export const metadata: Metadata = { title: "Start an application" };

export default function Page() {
  return <PortalNewPage />;
}
