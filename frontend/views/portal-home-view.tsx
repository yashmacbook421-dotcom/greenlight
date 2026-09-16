"use client";

import { FilePlus2, LogOut } from "lucide-react";

import { AppLink } from "@/components/app-link";
import { PortalStatusBadge } from "@/components/portal-ui";
import { Button, Panel } from "@/components/ui";
import type { PortalApplicationSummary } from "@/lib/types";

const ACTION: Record<string, string> = {
  draft: "Continue",
  action_required: "Fix and resubmit",
};

export function PortalHomePage({
  installer,
  applications,
  onSignOut,
}: {
  installer: string;
  applications: PortalApplicationSummary[];
  onSignOut: () => void;
}) {
  const waiting = applications.filter((a) => a.status === "draft" || a.status === "action_required").length;
  return (
    <>
      <header className="page-head">
        <div>
          <div className="eyebrow">{installer.toUpperCase()}</div>
          <h1>My applications</h1>
          <p>
            {applications.length === 0
              ? "Nothing submitted yet."
              : waiting > 0
                ? `${waiting} ${waiting === 1 ? "application needs" : "applications need"} something from you.`
                : "Nothing is waiting on you right now."}
          </p>
        </div>
        <div className="row gap">
          <Button variant="ghost" onClick={onSignOut}>
            <LogOut size={15} /> Switch installer
          </Button>
          <AppLink to="/portal/new" className="site-cta">
            <FilePlus2 size={16} /> Start an application
          </AppLink>
        </div>
      </header>
      {applications.length === 0 ? (
        <Panel className="portal-empty">
          <h2>Start your first application</h2>
          <p className="muted">
            It takes a few minutes: the customer and site, then three PDFs. You can save a draft and come back.
          </p>
          <AppLink to="/portal/new" className="site-cta">
            Start an application
          </AppLink>
        </Panel>
      ) : (
        <Panel className="portal-list">
          {applications.map((a) => (
            <AppLink key={a.id} to={`/portal/applications/${a.id}`} className={`portal-row status-${a.status}`}>
              <span className="portal-row-main">
                <strong>{a.applicant_name}</strong>
                <small>{a.site_address}</small>
              </span>
              <span className="portal-row-ref">
                <code>{a.reference}</code>
                <small>
                  Updated {new Date(a.updated_at).toLocaleDateString()} · {a.documents} document{a.documents === 1 ? "" : "s"}
                </small>
              </span>
              <PortalStatusBadge status={a.status} label={a.status_label} />
              <span className="portal-row-action">{ACTION[a.status] ?? "View"}</span>
            </AppLink>
          ))}
        </Panel>
      )}
    </>
  );
}
