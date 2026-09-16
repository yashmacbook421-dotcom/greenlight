import type { Metadata } from "next";

import { ReviewRoute } from "./route-client";

export const metadata: Metadata = { title: "Application Review" };

export default async function Page({ params }: PageProps<"/review/[id]">) {
  const { id } = await params;
  return <ReviewRoute id={id} />;
}
