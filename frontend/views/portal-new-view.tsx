"use client";

import { useState } from "react";

import { useAppNavigate } from "@/components/app-link";
import { SignInCard } from "@/components/portal-ui";
import { Button, Field, Panel } from "@/components/ui";
import { startPortalApplication } from "@/lib/api";
import { useInstaller } from "@/lib/installer";

export function PortalNewPage() {
  const { installer, ready, signIn } = useInstaller();
  const [form, setForm] = useState({ applicant_name: "", site_address: "", contact_email: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const navigate = useAppNavigate();
  if (!ready) return null;
  if (!installer)
    return (
      <div className="portal-page narrow">
        <SignInCard onSignIn={signIn} />
      </div>
    );

  return (
    <div className="portal-page narrow">
      <header className="page-head">
        <div>
          <div className="eyebrow">STEP 1 OF 3 · CUSTOMER AND SITE</div>
          <h1>Start an application</h1>
          <p>This creates a draft. You&apos;ll upload the documents next, and nothing is sent until you submit.</p>
        </div>
      </header>
      <ol className="wizard-steps" aria-label="Application steps">
        <li className="current">Customer and site</li>
        <li>Documents</li>
        <li>Submit</li>
      </ol>
      <Panel>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              const app = await startPortalApplication({
                installer,
                ...form,
                contact_email: form.contact_email.trim() || undefined,
              });
              navigate(`/portal/applications/${app.id}`);
            } catch (err) {
              setError(err instanceof Error ? err.message : "Could not start the application");
              setBusy(false);
            }
          }}
        >
          <Field label="Utility">
            <input value="Pacific Gas and Electric (PG&E)" disabled />
          </Field>
          <Field label="Installer">
            <input value={installer} disabled />
          </Field>
          <Field label="Customer of record">
            <input
              required
              value={form.applicant_name}
              onChange={(e) => setForm({ ...form, applicant_name: e.target.value })}
              placeholder="Name on the utility account"
            />
          </Field>
          <Field label="Service address">
            <input
              required
              value={form.site_address}
              onChange={(e) => setForm({ ...form, site_address: e.target.value })}
              placeholder="Where the system is installed"
            />
          </Field>
          <Field label="Contact email for updates">
            <input
              type="email"
              value={form.contact_email}
              onChange={(e) => setForm({ ...form, contact_email: e.target.value })}
              placeholder="Where the decision notice is sent"
            />
          </Field>
          {error && <div className="error-box">{error}</div>}
          <div className="form-actions">
            <Button type="submit" disabled={busy || !form.applicant_name.trim() || !form.site_address.trim()}>
              {busy ? "Creating draft…" : "Continue to documents"}
            </Button>
          </div>
        </form>
      </Panel>
    </div>
  );
}
