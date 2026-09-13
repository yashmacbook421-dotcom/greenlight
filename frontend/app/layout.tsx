import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Greenlight",
  description: "DER interconnection applications, reviewed by an agent, approved by a human.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-slate-50 text-slate-900">
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-[1400px] items-center gap-8 px-6 py-3">
            <Link href="/queue" className="flex items-center gap-2 font-semibold tracking-tight">
              <span className="inline-block h-3 w-3 rounded-full bg-emerald-500" aria-hidden />
              Greenlight
            </Link>
            <nav className="flex gap-5 text-sm text-slate-600">
              <Link href="/queue" className="hover:text-slate-900">Queue</Link>
              <Link href="/evals" className="hover:text-slate-900">Evals</Link>
            </nav>
            <span className="ml-auto text-xs text-slate-500">PG&amp;E Electric Rule 21 · effective 2025-08-29</span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-[1400px] flex-1 px-6 py-6">{children}</main>
      </body>
    </html>
  );
}
