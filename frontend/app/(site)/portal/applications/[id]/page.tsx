import type { Metadata } from "next";

import { PortalApplicationRoute } from "./route-client";

export const metadata: Metadata = { title: "Application" };

export default async function Page({ params }: PageProps<"/portal/applications/[id]">) {
  const { id } = await params;
  return <PortalApplicationRoute id={id} />;
}
