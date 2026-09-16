"use client";

import type { ReactNode } from "react";
import { ArrowUpRight } from "lucide-react";

import { AppLink } from "./app-link";

export function SiteShell({ children }: { children: ReactNode }) {
  return (
    <div className="site">
      <div className="site-banner">
        Demonstration site. Applications go to a local Greenlight instance, not to PG&amp;E, and sign-in is not verified.
      </div>
      <header className="site-header">
        <AppLink to="/" className="brand site-brand">
          <span className="brand-mark">G</span>
          <span>Greenlight</span>
        </AppLink>
        <nav className="site-nav">
          <AppLink to="/#how-it-works" className="site-link">
            How it works
          </AppLink>
          <AppLink to="/portal" className="site-link" activeProps={{ className: "active" }}>
            My applications
          </AppLink>
          <AppLink to="/portal/new" className="site-cta">
            Start an application
          </AppLink>
        </nav>
        <AppLink to="/queue" className="site-staff">
          Utility staff
          <ArrowUpRight size={14} />
        </AppLink>
      </header>
      <main className="site-main">{children}</main>
      <footer className="site-footer">
        <span>Greenlight · Electric Rule 21 interconnection review</span>
        <span>
          <AppLink to="/about">How the review engine works</AppLink> · <AppLink to="/queue">Engineer workspace</AppLink>
        </span>
      </footer>
    </div>
  );
}
