import type { Metadata } from "next";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Greenlight", template: "%s — Greenlight" },
  description: "Solar interconnection applications: submitted by installers, reviewed with AI, decided by engineers.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>{children}</body>
    </html>
  );
}
