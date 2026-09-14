"use client";

import { useState } from "react";
import { Check, FileUp, TriangleAlert } from "lucide-react";
import type { CaseDocument, DocumentKind } from "@/lib/types";
import { createApplication, runReview, uploadDocument } from "@/lib/api";
import { useAppNavigate } from "@/components/app-link";
import { Badge, Button, Field, Panel } from "@/components/ui";
const required: DocumentKind[] = ["application_form", "one_line_diagram", "inverter_spec_sheet"];
const kinds: DocumentKind[] = [
  ...required,
  "site_plan",
  "battery_spec_sheet",
  "customer_authorization",
  "other",
];
export function NewPage() {
  const [form, setForm] = useState({
    utility: "PGE",
    submitter: "",
    applicant_name: "",
    site_address: "",
  });
  const [caseId, setCaseId] = useState("");
  const [docs, setDocs] = useState<CaseDocument[]>([]);
  const [kind, setKind] = useState<DocumentKind>("application_form");
  const [llm, setLlm] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const nav = useAppNavigate();
  const missing = required.filter((r) => !docs.some((d) => d.kind === r));
  return (
    <div className="page narrow">
      <header className="page-head">
        <div>
          <div className="eyebrow">INSTALLER PACKET</div>
          <h1>New application</h1>
          <p>Create the case, add its PDFs, then run the first review.</p>
        </div>
      </header>
      <Panel title="1. Application details">
        <div className="form-grid">
          <Field label="Utility">
            <input
              value={form.utility}
              required
              onChange={(e) => setForm({ ...form, utility: e.target.value })}
            />
          </Field>
          <Field label="Submitter">
            <input
              value={form.submitter}
              onChange={(e) => setForm({ ...form, submitter: e.target.value })}
            />
          </Field>
          <Field label="Applicant name">
            <input
              value={form.applicant_name}
              onChange={(e) => setForm({ ...form, applicant_name: e.target.value })}
            />
          </Field>
          <Field label="Site address">
            <input
              value={form.site_address}
              onChange={(e) => setForm({ ...form, site_address: e.target.value })}
            />
          </Field>
        </div>
        <Button
          disabled={!form.utility || !!caseId}
          onClick={async () => {
            try {
              setError("");
              const r = await createApplication(form);
              setCaseId(r.case_id);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Could not create application");
            }
          }}
        >
          {caseId ? (
            <>
              <Check size={16} />
              Application created
            </>
          ) : (
            "Create application"
          )}
        </Button>
      </Panel>
      <Panel title="2. Documents">
        <div className="checklist">
          {required.map((r) => (
            <div key={r}>
              {docs.some((d) => d.kind === r) ? <Check size={16} /> : <span />}
              <strong>{r.replaceAll("_", " ")}</strong>
              <Badge tone={docs.some((d) => d.kind === r) ? "green" : "amber"}>
                {docs.some((d) => d.kind === r) ? "Uploaded" : "Required"}
              </Badge>
            </div>
          ))}
        </div>
        <div className="upload">
          <select value={kind} onChange={(e) => setKind(e.target.value as DocumentKind)}>
            {kinds.map((k) => (
              <option key={k} value={k}>
                {k.replaceAll("_", " ")}
              </option>
            ))}
          </select>
          <label className={caseId ? "file-button" : "file-button disabled"}>
            <FileUp size={17} />
            Choose PDF
            <input
              type="file"
              accept="application/pdf"
              disabled={!caseId}
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                try {
                  setError("");
                  const d = await uploadDocument(caseId, kind, file);
                  setDocs((v) => (v.some((x) => x.sha256 === d.sha256) ? v : [...v, d]));
                } catch (e) {
                  setError(e instanceof Error ? e.message : "Upload failed");
                }
              }}
            />
          </label>
        </div>
        {docs.map((d) => (
          <div className="uploaded" key={d.id}>
            <FileUp size={16} />
            <span>
              <strong>{d.filename}</strong>
              <small>
                {d.kind.replaceAll("_", " ")} · {d.page_count} pages
              </small>
            </span>
            <Badge tone="green">Ready</Badge>
          </div>
        ))}
      </Panel>
      <Panel title="3. Run review">
        <label className="check">
          <input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} /> Use
          Claude to read and draft
        </label>
        {!llm && (
          <div className="warning">
            <TriangleAlert size={17} />
            Without Claude, no facts are extracted from uploaded PDFs, so the review will be mostly
            inconclusive.
          </div>
        )}
        {missing.length > 0 && (
          <p className="notice">
            Missing documents will be listed in a deficiency notice:{" "}
            {missing.map((m) => m.replaceAll("_", " ")).join(", ")}.
          </p>
        )}
        <Button
          disabled={!caseId || busy}
          onClick={async () => {
            setBusy(true);
            try {
              await runReview(caseId, llm);
              nav(`/review/${caseId}`);
            } catch (e) {
              setError(e instanceof Error ? e.message : "Review failed");
              setBusy(false);
            }
          }}
        >
          {busy ? "Reviewing packet…" : "Run review"}
        </Button>
        {error && <div className="error-box">{error}</div>}
      </Panel>
    </div>
  );
}
