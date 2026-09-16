import type { Metadata } from "next";

import { HomePage } from "@/views/home-view";

export const metadata: Metadata = { title: { absolute: "Greenlight — Connect solar to the grid" } };

export default function Page() {
  return <HomePage />;
}
