import type { Metadata } from "next";

import { AboutRoute } from "./route-client";

export const metadata: Metadata = {
  title: "How Greenlight Works",
  description: "How Greenlight combines AI interpretation, deterministic Rule 21 checks, and engineer approval.",
  openGraph: {
    title: "How Greenlight Works",
    description: "Trustworthy automation for regulated interconnection reviews.",
    type: "website",
  },
};

export default function Page() {
  return <AboutRoute />;
}
