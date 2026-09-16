"use client";

import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, Clock, ExternalLink, FileText, FileUp, History, Loader2, Mail, Send, TriangleAlert } from "lucide-react";

import { AppLink } from "@/components/app-link";
import { PortalStatusBadge, statusTone } from "@/components/portal-ui";
import { Badge, Button, Panel } from "@/components/ui";
import { documentFileUrl, getPortalApplication, submitPortalApplication, uploadPortalDocument } from "@/lib/api";
import type { DocumentKind, PortalApplication, PortalDocument } from "@/lib/types";

const OPTIONAL: { kind: DocumentKind; label: string }[] = [
  { kind: "site_plan", label: "Site plan" },
  { kind: "battery_spec_sheet", label: "Battery specification sheet" },
  { kind: "customer_authorization", label: "Customer authorization" },
  { kind: "other", label: "Other supporting document" },
];
const STAGES = ["Prepare", "Submit", "Utility review", "Decision"];
const POLL_MS = 8000;

const when = (iso: string) =>
  new Date(iso).toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

function stageOf(app: PortalApplication): number {
  if (app.status === "draft") return 0;
  if (app.status === "under_review") return 2;
  return 3;
}

export function PortalApplicationPage({ initial }: { initial: PortalApplication }) {
  const [app, setApp] = useState(initial);
  const [busyKind, setBusyKind] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [extraKind, setExtraKind] = useState<DocumentKind>("site_plan");

  // While the utility is reviewing, check back so the decision shows up without a manual refresh.
  useEffect(() => {
    if (app.status !== "under_review") return;
    const timer = setInterval(() => {
      getPortalApplication(app.id).then(setApp, () => {});
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [app.id, app.status]);

  const upload = async (kind: DocumentKind, file: File | undefined) => {
    if (!file) return;
    setBusyKind(kind);
    setError("");
    try {
      setApp(await uploadPortalDocument(app.id, kind, file));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Upload failed");
    } finally {
      setBusyKind(null);
    }
  };

  const submit = async () => {
    setSubmitting(true);
    setError("");
    try {
      setApp(await submitPortalApplication(app.id));
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  // The newest letter is the current decision only once the review is over; after a resubmission it is history.
  const decided = app.status !== "draft" && app.status !== "under_review";
  const latestLetter = decided ? app.letters[0] : undefined;
  const earlierLetters = decided ? app.letters.slice(1) : app.letters;
  const correcting = app.status === "action_required";
  const stage = stageOf(app);
  const byKind = (kind: DocumentKind) => app.documents.filter((d) => d.kind === kind);
  const optionalDocs = app.documents.filter((d) => !app.required_documents.some((r) => r.kind === d.kind));

  return (
    <>
      <div className="breadcrumbs">
        <AppLink to="/portal">My applications</AppLink>
        <span>/</span>
        <span>{app.reference}</span>
      </div>

      <header className="page-head">
        <div>
          <div className="eyebrow">
            {app.reference} · {app.utility === "PGE" ? "PG&E" : app.utility}
          </div>
          <h1>{app.applicant_name}</h1>
          <p>{app.site_address}</p>
        </div>
        <PortalStatusBadge status={app.status} label={app.status_label} />
      </header>

      <ol className="stage-track" aria-label="Application progress">
        {STAGES.map((s, i) => (
          <li
            key={s}
            className={i < stage ? "done" : i === stage ? `current tone-${statusTone(app.status)}` : ""}
            aria-current={i === stage ? "step" : undefined}
          >
            <span>{i < stage ? <Check size={14} /> : i + 1}</span>
            {i === 3 && stage === 3 ? app.status_label : s}
          </li>
        ))}
      </ol>

      <div className={`status-callout tone-${statusTone(app.status)}`}>
        {app.status === "under_review" ? (
          <Loader2 size={20} className="spin" />
        ) : correcting ? (
          <TriangleAlert size={20} />
        ) : app.status === "draft" ? (
          <FileUp size={20} />
        ) : (
          <Check size={20} />
        )}
        <div>
          <strong>{app.status_label}</strong>
          <p>{app.status_detail}</p>
          {app.status === "under_review" && (
            <small>This page checks for updates automatically.</small>
          )}
        </div>
      </div>

      <div className="portal-grid">
        <div>
          {latestLetter && (
            <Panel
              title={correcting ? "Deficiency notice: what to fix" : "Decision letter"}
              action={<small>Issued {when(latestLetter.issued_at)} by {latestLetter.issued_by}</small>}
              className={correcting ? "letter-panel attention" : "letter-panel"}
            >
              <div className="markdown portal-letter">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{latestLetter.letter_md}</ReactMarkdown>
              </div>
            </Panel>
          )}

          <Panel
            title={correcting ? "Upload corrected documents" : "Documents"}
            action={
              app.can_upload ? (
                <small>PDF, up to 25 MB. Uploading again replaces that document.</small>
              ) : (
                <small>{app.status === "under_review" ? "Locked while the utility reviews them" : "Locked"}</small>
              )
            }
          >
            <div className="doc-list">
              {app.required_documents.map((r) => (
                <DocRow
                  key={r.kind}
                  label={r.label}
                  required
                  docs={byKind(r.kind)}
                  appId={app.id}
                  canUpload={app.can_upload}
                  busy={busyKind === r.kind}
                  onFile={(f) => upload(r.kind, f)}
                />
              ))}
              {optionalDocs.map((d) => (
                <DocRow
                  key={d.id}
                  label={d.label}
                  docs={[d]}
                  appId={app.id}
                  canUpload={app.can_upload && d.kind !== "other"}
                  busy={busyKind === d.kind}
                  onFile={(f) => upload(d.kind, f)}
                />
              ))}
            </div>
            {app.can_upload && (
              <div className="doc-extra">
                <span>Add an optional document</span>
                <select value={extraKind} onChange={(e) => setExtraKind(e.target.value as DocumentKind)}>
                  {OPTIONAL.map((o) => (
                    <option key={o.kind} value={o.kind}>
                      {o.label}
                    </option>
                  ))}
                </select>
                <FilePicker busy={busyKind === extraKind} label="Choose PDF" onFile={(f) => upload(extraKind, f)} />
              </div>
            )}
            {app.replaced_documents.length > 0 && (
              <details className="earlier">
                <summary>
                  <History size={14} /> Earlier versions ({app.replaced_documents.length})
                </summary>
                {app.replaced_documents.map((d) => (
                  <a key={d.id} href={documentFileUrl(app.id, d.id)} target="_blank" rel="noreferrer">
                    {d.label}: {d.filename} <small>replaced {when(d.replaced_at!)}</small>
                  </a>
                ))}
              </details>
            )}
          </Panel>

          {(app.status === "draft" || correcting) && (
            <Panel title={correcting ? "Resubmit" : "Submit to the utility"} className="submit-panel">
              <p className="muted">
                {correcting
                  ? "When your corrections are uploaded, resubmit. The application goes back through review, and the new decision will appear here."
                  : "Once submitted, documents are locked while the utility reviews them. You'll be notified here of the decision."}
              </p>
              {app.submit_blocker && (
                <div className="notice">
                  <TriangleAlert size={16} />
                  {app.submit_blocker}
                </div>
              )}
              <Button disabled={!app.can_submit || submitting} onClick={submit}>
                <Send size={16} />
                {submitting ? "Submitting…" : correcting ? "Resubmit with corrections" : "Submit application"}
              </Button>
            </Panel>
          )}
          {error && <div className="error-box">{error}</div>}
        </div>

        <aside>
          <Panel title="Activity">
            <ol className="activity">
              {[...app.timeline].reverse().map((t, i) => (
                <li key={`${t.at}-${i}`} className={`activity-${t.kind}`}>
                  <span className="activity-dot" />
                  <div>
                    <strong>{t.label}</strong>
                    {t.detail && <span>{t.detail}</span>}
                    <small>{when(t.at)}</small>
                  </div>
                </li>
              ))}
            </ol>
          </Panel>
          {earlierLetters.length > 0 && (
            <Panel title={decided ? "Earlier letters" : "Previous letters"}>
              {earlierLetters.map((l) => (
                <details key={l.id} className="earlier-letter">
                  <summary>
                    <Badge tone={statusTone(l.outcome)}>{l.outcome_label}</Badge>
                    <small>{when(l.issued_at)}</small>
                  </summary>
                  <div className="markdown">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{l.letter_md}</ReactMarkdown>
                  </div>
                </details>
              ))}
            </Panel>
          )}
          {app.notifications.length > 0 && (
            <Panel title="Updates sent to you">
              <ul className="notice-list">
                {app.notifications.map((n) => (
                  <li key={`${n.created_at}-${n.subject}`}>
                    <Mail size={15} />
                    <div>
                      <strong>{n.subject}</strong>
                      <span>
                        {n.status === "sent"
                          ? `Emailed to ${n.recipient}`
                          : n.status === "queued"
                            ? `Queued for ${n.recipient} — this demo has no mail server, so nothing was actually sent`
                            : n.status === "no_recipient"
                              ? "No contact email on this application, so nothing could be sent"
                              : `Could not be delivered to ${n.recipient}`}
                      </span>
                      <small>{when(n.sent_at ?? n.created_at)}</small>
                    </div>
                  </li>
                ))}
              </ul>
            </Panel>
          )}
          <Panel title="Details">
            <dl className="details">
              <dt>Installer</dt>
              <dd>{app.installer}</dd>
              <dt>Contact email</dt>
              <dd>{app.contact_email ?? "Not provided"}</dd>
              <dt>Started</dt>
              <dd>{when(app.started_at)}</dd>
              <dt>First submitted</dt>
              <dd>{app.submitted_at ? when(app.submitted_at) : "Not yet"}</dd>
            </dl>
          </Panel>
        </aside>
      </div>
    </>
  );
}

function DocRow({
  label,
  required,
  docs,
  appId,
  canUpload,
  busy,
  onFile,
}: {
  label: string;
  required?: boolean;
  docs: PortalDocument[];
  appId: string;
  canUpload: boolean;
  busy: boolean;
  onFile: (f: File | undefined) => void;
}) {
  const doc = docs.at(-1);
  return (
    <div className={`doc-row ${doc ? "has-doc" : ""}`}>
      <span className="doc-state">{doc ? <Check size={16} /> : required ? <Clock size={16} /> : <FileText size={16} />}</span>
      <span className="doc-main">
        <strong>
          {label} {required && !doc && <Badge tone="amber">Required</Badge>}
        </strong>
        {doc ? (
          <a href={documentFileUrl(appId, doc.id)} target="_blank" rel="noreferrer">
            {doc.filename} · {doc.page_count} page{doc.page_count === 1 ? "" : "s"} <ExternalLink size={12} />
          </a>
        ) : (
          <small>Not uploaded</small>
        )}
      </span>
      {canUpload && <FilePicker busy={busy} label={doc ? "Replace" : "Upload"} secondary={!!doc} onFile={onFile} />}
    </div>
  );
}

function FilePicker({
  busy,
  label,
  secondary,
  onFile,
}: {
  busy: boolean;
  label: string;
  secondary?: boolean;
  onFile: (f: File | undefined) => void;
}) {
  return (
    <label className={`file-button ${secondary ? "secondary" : ""} ${busy ? "disabled" : ""}`}>
      {busy ? <Loader2 size={15} className="spin" /> : <FileUp size={15} />}
      {busy ? "Uploading…" : label}
      <input
        type="file"
        accept="application/pdf"
        disabled={busy}
        onChange={(e) => {
          onFile(e.target.files?.[0]);
          e.target.value = "";
        }}
      />
    </label>
  );
}
