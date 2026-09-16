"use client";

import { useState } from "react";
import { Building2 } from "lucide-react";

import type { PortalStatus } from "@/lib/types";
import { SAMPLE_INSTALLER } from "@/lib/installer";
import { Badge, Button, Field, Panel } from "./ui";

const TONE: Record<PortalStatus, "green" | "amber" | "red" | "blue" | "neutral"> = {
  draft: "neutral",
  under_review: "blue",
  action_required: "amber",
  passed_initial_review: "green",
  supplemental_review: "red",
  engineering_review: "blue",
};

export function PortalStatusBadge({ status, label }: { status: PortalStatus; label: string }) {
  return <Badge tone={TONE[status]}>{label}</Badge>;
}

export function statusTone(status: PortalStatus) {
  return TONE[status];
}

export function SignInCard({ onSignIn }: { onSignIn: (installer: string) => void }) {
  const [name, setName] = useState("");
  return (
    <Panel className="portal-signin">
      <Building2 size={26} />
      <h1>Sign in as an installer</h1>
      <p className="muted">
        Your applications are listed under your company name. This demo has no passwords: type any company name.
      </p>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (name.trim()) onSignIn(name);
        }}
      >
        <Field label="Installer company">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Sunrise Solar Inc." autoFocus />
        </Field>
        <Button type="submit" disabled={!name.trim()}>
          Continue
        </Button>
      </form>
      <button className="text-link" onClick={() => onSignIn(SAMPLE_INSTALLER)}>
        Use the sample installer ({SAMPLE_INSTALLER})
      </button>
    </Panel>
  );
}
