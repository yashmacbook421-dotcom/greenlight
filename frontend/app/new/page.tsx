import type { Metadata } from "next";

import { NewPage } from "@/views/new-view";

export const metadata: Metadata = { title: "New Application" };

export default function Page() {
  return <NewPage />;
}
