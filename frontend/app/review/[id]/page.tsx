"use client";

import Link from "next/link";
import { use, useCallback, useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Cite, DispositionBadge, ReviewStatusBadge, StatusBadge } from "@/components/badges";
import { API_URL, DISPOSITION_LABEL, api, type Item, type Proposal, type ReviewBundle, type ScreenRow } from "@/lib/api";

type Focus = { kind: Item["basis_kind"]; ref: string } | null;

const VERDICT_LABEL: Record<string, string> = {
  disposition_veto: "Disposition floor",
  provenance_completeness: "Items backed by evidence",
  number_faithfulness: "Numbers traceable to evidence",
  citation_validity: "Citations resolve to Rule 21 text",
  fail_closed: "Fail-closed hold",
};

function evidenceId(kind: string, ref: string) {
  return `ev-${kind}-${ref}`.replace(/[^\w-]/g, "_");
}

export default function ReviewPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [bundle, setBundle] = useState<ReviewBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [focus, setFocus] = useState<Focus>(null);

  const load = useCallback(async () => {
    try {
      setBundle(await api<ReviewBundle>(`/cases/${id}/review`));
    } catch (e) {
      setError((e as Error).message);
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch of external data
    load();
  }, [load]);

  useEffect(() => {
    if (!focus) return;
    document.getElementById(evidenceId(focus.kind, focus.ref))?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [focus]);

  if (error) return <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>;
  if (!bundle) return <p className="text-sm text-slate-500">Loading review…</p>;

  const p = bundle.proposal;
  const isFocused = (kind: string, ref: string) => focus?.kind === kind && focus.ref === ref;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link href="/queue" className="text-xs text-slate-500 hover:text-slate-800">← Queue</Link>
          <h1 className="mt-1 text-xl font-semibold tracking-tight">{bundle.application?.applicant_name ?? "Application"}</h1>
          <p className="text-sm text-slate-600">
            {bundle.application?.site_address} · submitted by {bundle.case.submitter ?? "unknown"} · {bundle.application?.utility}
          </p>
        </div>
        {p && (
          <div className="flex items-center gap-3">
            <DispositionBadge disposition={p.disposition} />
            <ReviewStatusBadge status={p.status} />
            {p.agent_run_id ? (
              <Link href={`/trace/${id}`} className="text-sm font-medium text-emerald-700 hover:text-emerald-900">Agent trace →</Link>
            ) : (
              <span className="text-xs text-slate-500">template draft (no agent)</span>
            )}
          </div>
        )}
      </div>

      {!p && <p className="text-sm text-slate-600">No draft yet. Run a review from the queue.</p>}

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        {/* Left: the claim */}
        <div className="space-y-5">
          {p && <Guardrails proposal={p} />}
          {p && p.items.length > 0 && (
            <section className="rounded-lg border border-slate-200 bg-white">
              <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">Deficiency items ({p.items.length})</h2>
              <ol className="divide-y divide-slate-100">
                {p.items.map((item, i) => (
                  <li key={i} className="px-4 py-3 text-sm">
                    <p className="leading-relaxed">{item.description}</p>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                      <button onClick={() => setFocus({ kind: item.basis_kind, ref: item.basis_ref })}
                              className="rounded border border-emerald-300 bg-emerald-50 px-1.5 py-0.5 font-medium text-emerald-800 hover:bg-emerald-100">
                        evidence: {item.basis_kind.replace("_", " ")} {item.basis_kind === "fact" ? "" : item.basis_ref} ↗
                      </button>
                      {item.rule_section && item.rule_sheet && <Cite section={item.rule_section} sheet={item.rule_sheet} />}
                    </div>
                  </li>
                ))}
              </ol>
            </section>
          )}
          {p && (
            <section className="rounded-lg border border-slate-200 bg-white">
              <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">Draft letter</h2>
              <div className="letter max-h-[70vh] overflow-y-auto px-5 py-3 text-sm">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{p.letter_md}</ReactMarkdown>
              </div>
            </section>
          )}
          {p && <DecisionPanel proposal={p} onDone={load} />}
        </div>

        {/* Right: the evidence */}
        <div className="space-y-5">
          <section className="rounded-lg border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">Initial Review screens</h2>
            <div className="divide-y divide-slate-100">
              {bundle.screens.map((s) => (
                <ScreenLine key={s.screen} s={s} focused={isFocused("screen", s.screen)} />
              ))}
            </div>
          </section>

          {bundle.discrepancies.length > 0 && (
            <section className="rounded-lg border border-slate-200 bg-white">
              <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">Conflicts across documents</h2>
              <div className="divide-y divide-slate-100">
                {bundle.discrepancies.map((d) => (
                  <div key={d.field} id={evidenceId("discrepancy", d.field)}
                       className={`px-4 py-3 text-sm ${isFocused("discrepancy", d.field) ? "bg-emerald-50 ring-2 ring-emerald-400 ring-inset" : ""}`}>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-xs">{d.field}</span>
                      <span className={`text-xs font-medium ${d.material ? "text-rose-700" : d.material === false ? "text-emerald-700" : "text-amber-700"}`}>
                        {d.material ? "material" : d.material === false ? "immaterial" : "unjudged"}
                      </span>
                      {d.method && <span className="text-xs text-slate-500">judged by {d.method === "llm" ? "Claude" : "re-running the screens"}</span>}
                    </div>
                    <div className="mt-1 flex flex-wrap gap-2">
                      {d.observed.map((o, i) => (
                        <span key={i} className={`rounded px-1.5 py-0.5 font-mono text-xs ${o.chosen ? "bg-slate-800 text-white" : "bg-slate-100"}`}
                              title={o.sources.map((s) => s.derivation ?? "stated").join("; ")}>
                          {String(o.value)}
                        </span>
                      ))}
                    </div>
                    {d.rationale && <p className="mt-1 text-xs text-slate-600">{d.rationale}</p>}
                  </div>
                ))}
              </div>
            </section>
          )}

          <section className="rounded-lg border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">What the documents say</h2>
            {bundle.documents.map((doc) => {
              const facts = bundle.facts.filter((f) => f.document_id === doc.id);
              return (
                <div key={doc.id} id={evidenceId("missing_document", doc.kind)} className="border-b border-slate-100 last:border-0">
                  <div className="flex items-center justify-between bg-slate-50 px-4 py-2 text-xs">
                    <span className="font-medium text-slate-700">{doc.kind.replaceAll("_", " ")} · {doc.page_count} page(s)
                      {doc.pages.some((pg) => !pg.has_text_layer) && <span className="ml-2 text-amber-700">scanned</span>}
                    </span>
                    <a href={`${API_URL}/cases/${id}/documents/${doc.id}/file`} target="_blank" rel="noreferrer"
                       className="text-emerald-700 hover:text-emerald-900">open PDF ↗</a>
                  </div>
                  <table className="w-full text-xs">
                    <tbody className="divide-y divide-slate-50">
                      {facts.map((f) => (
                        <tr key={f.id} id={evidenceId("fact", f.id)} className={isFocused("fact", f.id) ? "bg-emerald-50" : ""}>
                          <td className="w-44 px-4 py-1.5 font-mono text-slate-500">{f.field}</td>
                          <td className="px-2 py-1.5 font-medium">{f.value}{f.unit ? ` ${f.unit}` : ""}</td>
                          <td className="px-2 py-1.5 text-slate-600">&ldquo;{f.quote}&rdquo;</td>
                          <td className="px-4 py-1.5 text-right whitespace-nowrap">
                            <a href={`${API_URL}/cases/${id}/documents/${f.document_id}/file#page=${f.page_no}`} target="_blank" rel="noreferrer"
                               className="text-slate-500 hover:text-emerald-800">p.{f.page_no}</a>
                            {f.verification === "image_unverified" && <span className="ml-1 text-amber-700" title="from a scanned page; quote not machine-verified">⚠</span>}
                          </td>
                        </tr>
                      ))}
                      {facts.length === 0 && <tr><td className="px-4 py-2 text-slate-400">No facts extracted.</td></tr>}
                    </tbody>
                  </table>
                </div>
              );
            })}
            {bundle.documents.length === 0 && <p className="px-4 py-3 text-sm text-slate-500">No documents uploaded.</p>}
          </section>

          {bundle.scenarios.length > 0 && (
            <section className="rounded-lg border border-slate-200 bg-white">
              <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">What-if scenarios the agent ran</h2>
              {Object.entries(groupBy(bundle.scenarios, (s) => s.input_hash)).map(([hash, rows]) => (
                <div key={hash} className="border-b border-slate-100 px-4 py-2.5 text-xs last:border-0">
                  <p className="text-slate-700">{rows[0].overrides.rationale ?? "scenario"}</p>
                  <p className="mt-0.5 font-mono text-slate-500">
                    {Object.entries(rows[0].overrides).filter(([k]) => k !== "rationale").map(([k, v]) => `${k}=${v}`).join(", ")}
                  </p>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {rows.map((r) => <span key={r.screen} className="flex items-center gap-1"><b>{r.screen}</b><StatusBadge status={r.status} /></span>)}
                  </div>
                </div>
              ))}
            </section>
          )}
        </div>
      </div>
    </div>
  );
}

function groupBy<T>(xs: T[], key: (x: T) => string): Record<string, T[]> {
  return xs.reduce<Record<string, T[]>>((acc, x) => ((acc[key(x)] ??= []).push(x), acc), {});
}

function ScreenLine({ s, focused }: { s: ScreenRow; focused: boolean }) {
  const [open, setOpen] = useState(false);
  return (
    <div id={evidenceId("screen", s.screen)} className={focused ? "bg-emerald-50 ring-2 ring-emerald-400 ring-inset" : ""}>
      <button onClick={() => setOpen(!open)} className="flex w-full items-start gap-3 px-4 py-2 text-left text-sm hover:bg-slate-50">
        <span className="w-6 pt-0.5 font-mono text-xs font-semibold text-slate-700">{s.screen}</span>
        <StatusBadge status={s.status} />
        <span className="flex-1 text-slate-700">{s.reason}</span>
        {s.synthetic_inputs.length > 0 && <span className="text-[11px] text-amber-700" title={s.synthetic_inputs.join(", ")}>synthetic data</span>}
      </button>
      {open && (
        <div className="space-y-1.5 bg-slate-50 px-12 pb-3 pt-1 text-xs text-slate-600">
          {s.formula && <p><span className="text-slate-400">formula</span> <code>{s.formula}</code></p>}
          {(s.computed || s.threshold) && <p><span className="text-slate-400">computed</span> <b>{s.computed ?? "—"}</b> <span className="text-slate-400">threshold</span> <b>{s.threshold ?? "—"}</b></p>}
          {Object.keys(s.inputs).length > 0 && (
            <p className="font-mono">{Object.entries(s.inputs).map(([k, v]) => `${k}=${v}`).join(" · ")}</p>
          )}
          {s.missing_inputs.length > 0 && <p className="text-amber-800">missing: {s.missing_inputs.join(", ")} ({s.blocker} to supply)</p>}
          {s.routed_by && <p>routed by Screen {s.routed_by}</p>}
          <div className="flex flex-wrap gap-1.5">
            {s.citations.map((c, i) => <span key={i} title={c.quote}><Cite section={c.section} sheet={c.sheet} /></span>)}
          </div>
          {s.citations.filter((c) => c.interpretation).map((c, i) => (
            <p key={i} className="italic text-slate-500">Interpretation: {c.interpretation}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function Guardrails({ proposal }: { proposal: Proposal }) {
  const checks = proposal.guardrail_verdicts.filter((v) => v.name !== "summary_for_engineer");
  const summary = proposal.guardrail_verdicts.find((v) => v.name === "summary_for_engineer");
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">Code checks on this draft</h2>
      {proposal.model_disposition && (
        <p className="border-b border-rose-100 bg-rose-50 px-4 py-2 text-sm text-rose-800">
          The model proposed <b>{DISPOSITION_LABEL[proposal.model_disposition]}</b>; code raised it to{" "}
          <b>{DISPOSITION_LABEL[proposal.disposition]}</b>.
        </p>
      )}
      <ul className="divide-y divide-slate-100">
        {checks.map((v) => (
          <li key={v.name} className="flex items-start gap-3 px-4 py-2 text-sm">
            <span className={`mt-0.5 font-bold ${v.passed ? "text-emerald-600" : "text-rose-600"}`}>{v.passed ? "✓" : "✕"}</span>
            <div>
              <div className="font-medium">{VERDICT_LABEL[v.name] ?? v.name}</div>
              <div className="text-xs text-slate-600">{v.detail}</div>
            </div>
          </li>
        ))}
      </ul>
      {summary && <p className="border-t border-slate-100 px-4 py-2 text-xs text-slate-600"><b>Drafter&apos;s summary:</b> {summary.detail}</p>}
    </section>
  );
}

function DecisionPanel({ proposal, onDone }: { proposal: Proposal; onDone: () => void }) {
  const [reviewer, setReviewer] = useState("");
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [letter, setLetter] = useState(proposal.letter_md);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (proposal.status !== "pending_review") {
    return (
      <section className="rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm">
        <ReviewStatusBadge status={proposal.status} /> by <b>{proposal.reviewed_by}</b>{" "}
        on {proposal.reviewed_at ? new Date(proposal.reviewed_at).toLocaleString() : "—"}
        {proposal.review_note && <p className="mt-1 text-slate-600">Note: {proposal.review_note}</p>}
        <p className="mt-1 text-xs text-slate-500">Reviewed proposals are locked by the database.</p>
      </section>
    );
  }

  async function decide(action: "approve" | "edit" | "reject") {
    setBusy(true);
    setError(null);
    try {
      await api(`/proposals/${proposal.id}/decision`, {
        method: "POST",
        body: JSON.stringify({ action, reviewer, note: note || null, letter_md: action === "edit" ? letter : null }),
      });
      onDone();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const blocked = busy || reviewer.trim() === "";
  return (
    <section className="rounded-lg border-2 border-slate-800 bg-white">
      <h2 className="border-b border-slate-200 px-4 py-2.5 text-sm font-semibold">Engineer decision</h2>
      <div className="space-y-3 px-4 py-3 text-sm">
        <p className="text-xs text-slate-600">Nothing reaches the applicant until a named engineer approves or edits this draft.</p>
        <div className="flex flex-wrap gap-3">
          <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Your name"
                 className="w-48 rounded-md border border-slate-300 px-2 py-1.5" />
          <input value={note} onChange={(e) => setNote(e.target.value)} placeholder="Note (optional)"
                 className="min-w-48 flex-1 rounded-md border border-slate-300 px-2 py-1.5" />
        </div>
        {editing && (
          <textarea value={letter} onChange={(e) => setLetter(e.target.value)} rows={14}
                    className="w-full rounded-md border border-slate-300 p-2 font-mono text-xs" />
        )}
        {error && <p className="text-rose-700">{error}</p>}
        <div className="flex flex-wrap gap-2">
          <button onClick={() => decide("approve")} disabled={blocked || editing}
                  className="rounded-md bg-emerald-600 px-3 py-1.5 font-medium text-white hover:bg-emerald-700 disabled:opacity-40">
            Approve as drafted
          </button>
          {editing ? (
            <button onClick={() => decide("edit")} disabled={blocked || letter === proposal.letter_md}
                    className="rounded-md bg-slate-900 px-3 py-1.5 font-medium text-white hover:bg-slate-700 disabled:opacity-40">
              Save edited letter
            </button>
          ) : (
            <button onClick={() => setEditing(true)} className="rounded-md border border-slate-300 px-3 py-1.5 font-medium hover:bg-slate-50">
              Edit letter…
            </button>
          )}
          <button onClick={() => decide("reject")} disabled={blocked}
                  className="ml-auto rounded-md border border-rose-300 px-3 py-1.5 font-medium text-rose-700 hover:bg-rose-50 disabled:opacity-40">
            Reject draft
          </button>
        </div>
      </div>
    </section>
  );
}
