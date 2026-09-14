"use client";

import { useEffect, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Check, ChevronDown, ExternalLink, FileText, Search, X } from "lucide-react";
import type { Fact, Proposal, ProposalItem, ReviewBundle, RuleResult, Screen } from "@/lib/types";
import { decide, documentFileUrl, getDocumentPage, searchRules } from "@/lib/api";
import { AppLink } from "@/components/app-link";
import { Badge, Button, Field, Panel } from "@/components/ui";
import { DispositionBadge, ScreenBadge, TrustTag, VerdictIcon } from "@/components/status";

const pretty = (s: string) => s.replaceAll("_", " ").replace(/\b\w/g, (c) => c.toUpperCase());
const VERDICT_LABEL: Record<string, string> = {
  disposition_veto: "Disposition floor",
  provenance_completeness: "Items backed by evidence",
  number_faithfulness: "Numbers traceable to evidence",
  citation_validity: "Citations resolve to Rule 21 text",
  fail_closed: "Fail-closed hold",
};

function evidenceFor(item: ProposalItem, data: ReviewBundle): Fact[] {
  if (item.basis_kind === "fact") return data.facts.filter((f) => f.id === item.basis_ref);
  if (item.basis_kind === "discrepancy") {
    const d = data.discrepancies.find((x) => x.field === item.basis_ref);
    const ids = new Set(d?.observed.flatMap((o) => o.sources.flatMap((s) => s.fact_ids)) ?? []);
    return data.facts.filter((f) => ids.has(f.id));
  }
  return [];
}

/** Highlight a quote inside the ORIGINAL page text, matching case- and whitespace-insensitively. */
function highlightQuote(text: string, quote: string): ReactNode {
  const tokens = quote.trim().split(/\s+/).filter(Boolean).map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  if (!text || tokens.length === 0) return text;
  const match = new RegExp(tokens.join("\\s+"), "i").exec(text);
  if (!match) return text;
  return (
    <>
      {text.slice(0, match.index)}
      <mark>{match[0]}</mark>
      {text.slice(match.index + match[0].length)}
    </>
  );
}

/** Line diff (longest common subsequence); letters are short enough for O(n·m). */
function lineDiff(before: string, after: string): Array<{ kind: " " | "-" | "+"; line: string }> {
  const a = before.split("\n");
  const b = after.split("\n");
  const lcs = Array.from({ length: a.length + 1 }, () => new Array<number>(b.length + 1).fill(0));
  for (let i = a.length - 1; i >= 0; i--)
    for (let j = b.length - 1; j >= 0; j--)
      lcs[i][j] = a[i] === b[j] ? lcs[i + 1][j + 1] + 1 : Math.max(lcs[i + 1][j], lcs[i][j + 1]);
  const out: Array<{ kind: " " | "-" | "+"; line: string }> = [];
  let i = 0;
  let j = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      out.push({ kind: " ", line: a[i] });
      i++;
      j++;
    } else if (lcs[i + 1][j] >= lcs[i][j + 1]) out.push({ kind: "-", line: a[i++] });
    else out.push({ kind: "+", line: b[j++] });
  }
  while (i < a.length) out.push({ kind: "-", line: a[i++] });
  while (j < b.length) out.push({ kind: "+", line: b[j++] });
  return out;
}

export function ReviewPage({
  data,
  onUpdated,
}: {
  data: ReviewBundle;
  onUpdated: (d: ReviewBundle) => void;
}) {
  const [selected, setSelected] = useState<Fact | null>(null);
  const [page, setPage] = useState<{ factId: string; text: string } | null>(null);
  const pageText = selected && page?.factId === selected.id ? page.text : "";
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<RuleResult[]>([]);
  const [searchError, setSearchError] = useState("");
  const [help, setHelp] = useState(false);

  useEffect(() => {
    if (!selected) return;
    let cancelled = false;
    getDocumentPage(data.case.id, selected.document_id, selected.page_no)
      .then((p) => !cancelled && setPage({ factId: selected.id, text: p.has_text_layer ? p.text : "" }))
      .catch(() => !cancelled && setPage({ factId: selected.id, text: "Page text unavailable." }));
    return () => {
      cancelled = true;
    };
  }, [selected, data.case.id]);

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement)?.matches("input,textarea,select")) return;
      if (e.key === "?") setHelp((v) => !v);
      if (e.key === "Escape") {
        setHelp(false);
        setSelected(null);
      }
      if ((e.key === "j" || e.key === "k") && data.facts.length) {
        const i = selected ? data.facts.findIndex((f) => f.id === selected.id) : -1;
        const next = e.key === "j" ? Math.min(i + 1, data.facts.length - 1) : Math.max(i - 1, 0);
        setSelected(data.facts[next] ?? null);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [data.facts, selected]);

  const openScreen = (id: string) => {
    const el = document.getElementById(`screen-${id}`) as HTMLDetailsElement | null;
    if (el) {
      el.open = true;
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    }
  };

  const applicant = data.application?.applicant_name ?? "Applicant not provided";
  const submitter = data.case.submitter?.replace(/^\[[^\]]+\]\s*/, "") ?? "Submitter not provided";
  const proposal = data.proposal;
  const scenarios = useMemo(() => {
    const groups = new Map<string, Screen[]>();
    for (const s of data.scenarios) groups.set(s.input_hash, [...(groups.get(s.input_hash) ?? []), s]);
    return [...groups.values()];
  }, [data.scenarios]);

  return (
    <div className="page review">
      <div className="breadcrumbs">
        <AppLink to="/queue">Queue</AppLink>
        <span>/</span>
        <span>{applicant}</span>
      </div>
      <header className="page-head review-head">
        <div>
          <div className="eyebrow">CASE {data.case.id.slice(0, 8)}</div>
          <h1>{applicant}</h1>
          <p>
            {data.application?.site_address ?? "Site address not provided"} · {submitter}
          </p>
        </div>
        {proposal && (
          <div className="outcome">
            <span>Draft outcome</span>
            <DispositionBadge value={proposal.disposition} />
            <TrustTag kind="code" />
          </div>
        )}
      </header>
      <div className="trust-strip">
        <strong>Authority map</strong>
        <TrustTag kind="ai" />
        <span>Documents & letter</span>
        <TrustTag kind="code" />
        <span>Screens & guardrails</span>
        <Badge tone="neutral">Engineer decides</Badge>
        {proposal?.model_disposition && <TrustTag kind="override" />}
      </div>
      <div className="review-grid">
        <div className="review-main">
          {proposal ? (
            <ChecksAndItems proposal={proposal} data={data} onFact={setSelected} onScreen={openScreen} />
          ) : (
            <Panel title="No draft yet">
              <p className="muted">
                This application has not been reviewed. Run a review from the queue to draft an outcome.
              </p>
            </Panel>
          )}
          <Panel title="Rule 21 screens" action={<TrustTag kind="code" />}>
            {data.screens.length === 0 && <p className="muted">Screens run when the review runs.</p>}
            <div className="screens">
              {data.screens.map((s) => (
                <ScreenDetails key={s.screen} s={s} />
              ))}
            </div>
          </Panel>
          {data.discrepancies.length > 0 && (
            <Panel title="Conflicts across documents">
              {data.discrepancies.map((d) => (
                <article className="conflict" key={d.field}>
                  <div className="row between">
                    <h3>{pretty(d.field)}</h3>
                    <div className="row gap">
                      {d.method === "llm" ? <TrustTag kind="ai" /> : d.method === "rule_outcome" ? <TrustTag kind="code" /> : null}
                      <Badge tone={d.material ? "red" : d.material === false ? "neutral" : "amber"}>
                        {d.material ? "Material" : d.material === false ? "Not material" : "Not yet judged"}
                      </Badge>
                    </div>
                  </div>
                  <div className="observed">
                    {d.observed.map((o, i) => (
                      <div key={i} title={o.sources.map((s) => s.derivation ?? "stated in a document").join("; ")}>
                        <strong>{String(o.value)}</strong>
                        {o.chosen && <Badge tone="green">Used</Badge>}
                      </div>
                    ))}
                  </div>
                  <p>{d.rationale ?? "No judgment recorded; an engineer should decide whether this matters."}</p>
                </article>
              ))}
            </Panel>
          )}
          <Panel title="What the documents say" action={<Badge>{data.facts.length} facts</Badge>}>
            {data.facts.length === 0 && (
              <p className="muted">No facts extracted yet. Reviews with Claude extract facts from uploaded PDFs.</p>
            )}
            <div className="facts">
              {data.facts.map((f) => (
                <button className={selected?.id === f.id ? "active" : ""} key={f.id} onClick={() => setSelected(f)}>
                  <span>
                    <strong>{pretty(f.field)}</strong>
                    <small>
                      {pretty(f.document_kind)} · page {f.page_no}
                    </small>
                  </span>
                  <span className="fact-value">
                    {f.value_as_written ?? f.value} {f.value_as_written ? f.unit_as_written : f.unit}
                  </span>
                </button>
              ))}
            </div>
          </Panel>
          {scenarios.length > 0 && (
            <Panel title="What-if scenarios the agent ran" action={<TrustTag kind="code" />}>
              {scenarios.map((rows) => {
                const o = rows[0].overrides as Record<string, string>;
                return (
                  <article className="conflict" key={rows[0].input_hash}>
                    <h3>{o.rationale || "Scenario"}</h3>
                    <p className="muted">
                      {Object.entries(o)
                        .filter(([k]) => k !== "rationale")
                        .map(([k, v]) => `${pretty(k)} = ${v}`)
                        .join(" · ")}
                    </p>
                    <div className="row gap" style={{ flexWrap: "wrap" }}>
                      {rows.map((r) => (
                        <span key={r.screen} className="row gap">
                          <strong>{r.screen}</strong>
                          <ScreenBadge status={r.status} />
                        </span>
                      ))}
                    </div>
                  </article>
                );
              })}
            </Panel>
          )}
          <Panel title="Search the tariff">
            <form
              className="search-row"
              onSubmit={async (e) => {
                e.preventDefault();
                setSearchError("");
                try {
                  setResults(await searchRules(query, 5));
                } catch (err) {
                  setSearchError(err instanceof Error ? err.message : "Search failed");
                }
              }}
            >
              <Search size={17} />
              <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search Rule 21" />
              <Button type="submit" variant="secondary">
                Search
              </Button>
            </form>
            {searchError && <div className="error-box">{searchError}</div>}
            {results.map((r) => (
              <article className="rule-result" key={`${r.section}-${r.sheet}`}>
                <strong>
                  §{r.section} · Sheet {r.sheet}
                </strong>
                <p>{r.snippet.replaceAll("«", "").replaceAll("»", "")}</p>
              </article>
            ))}
          </Panel>
        </div>
        <aside className="review-aside">
          {proposal && (
            <>
              <Panel title="Draft letter">
                <div className="markdown">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{proposal.letter_md}</ReactMarkdown>
                </div>
              </Panel>
              <DecisionPanel
                key={proposal.id}
                proposal={proposal}
                onDecided={(p) => onUpdated({ ...data, case: { ...data.case, status: "closed" }, proposal: p })}
              />
              {proposal.agent_run_id ? (
                <AppLink className="trace-link" to={`/trace/${data.case.id}`}>
                  View agent trace <ExternalLink size={15} />
                </AppLink>
              ) : (
                <p className="muted">Drafted by template — no agent trace.</p>
              )}
            </>
          )}
        </aside>
      </div>
      {selected && (
        <div className="evidence-drawer">
          <div className="drawer-head">
            <div>
              <strong>{pretty(selected.field)}</strong>
              <span>
                {pretty(selected.document_kind)} · page {selected.page_no}
              </span>
            </div>
            <Button variant="ghost" onClick={() => setSelected(null)} aria-label="Close evidence">
              <X size={18} />
            </Button>
          </div>
          <div className="evidence-split">
            <iframe title="Source PDF" src={documentFileUrl(data.case.id, selected.document_id, selected.page_no)} />
            <div className="page-text">
              <Badge tone={selected.verification === "image_unverified" ? "amber" : "green"}>
                {selected.verification === "image_unverified"
                  ? "From a scanned page — not machine-verified"
                  : selected.verification === "oracle"
                    ? "Generated test fact (oracle)"
                    : "Text matched on page"}
              </Badge>
              <h3>Extracted page text</h3>
              {pageText ? (
                <p style={{ whiteSpace: "pre-wrap" }}>{highlightQuote(pageText, selected.quote)}</p>
              ) : (
                <p className="muted">This page has no text layer; only the quote is available.</p>
              )}
              <blockquote>{selected.quote}</blockquote>
            </div>
          </div>
        </div>
      )}
      {help && (
        <div className="modal-backdrop" onClick={() => setHelp(false)}>
          <div className="help" role="dialog" aria-label="Keyboard shortcuts" onClick={(e) => e.stopPropagation()}>
            <h2>Keyboard shortcuts</h2>
            <p>
              <kbd>j</kbd> Next fact
            </p>
            <p>
              <kbd>k</kbd> Previous fact
            </p>
            <p>
              <kbd>Esc</kbd> Close evidence or help
            </p>
            <p>
              <kbd>?</kbd> Open or close help
            </p>
            <Button onClick={() => setHelp(false)}>Done</Button>
          </div>
        </div>
      )}
    </div>
  );
}

function ChecksAndItems({
  proposal,
  data,
  onFact,
  onScreen,
}: {
  proposal: Proposal;
  data: ReviewBundle;
  onFact: (f: Fact) => void;
  onScreen: (id: string) => void;
}) {
  const checks = proposal.guardrail_verdicts.filter((v) => v.name !== "summary_for_engineer");
  const summary = proposal.guardrail_verdicts.find((v) => v.name === "summary_for_engineer");
  const fails = checks.filter((v) => !v.passed).length;
  return (
    <>
      <Panel
        title="Code checks on this draft"
        action={<Badge tone={fails ? "red" : "green"}>{fails ? `${fails} needs attention` : "All passed"}</Badge>}
      >
        {proposal.model_disposition && (
          <div className="error-box">
            The AI proposed {pretty(proposal.model_disposition.toLowerCase())}; code raised it to{" "}
            {pretty(proposal.disposition.toLowerCase())} because the evidence requires it.
          </div>
        )}
        <div className="verdict-grid">
          {checks.map((v) => (
            <div className="verdict" key={v.name}>
              <VerdictIcon passed={v.passed} />
              <div>
                <strong>{VERDICT_LABEL[v.name] ?? pretty(v.name)}</strong>
                <p>{v.detail}</p>
              </div>
            </div>
          ))}
        </div>
        {summary && (
          <p className="muted">
            <strong>Drafter&apos;s summary:</strong> {summary.detail}
          </p>
        )}
      </Panel>
      {proposal.items.length > 0 && (
        <Panel title="Items to resolve">
          <div className="item-list">
            {proposal.items.map((item, i) => {
              const evidence = evidenceFor(item, data);
              return (
                <article className="deficiency" key={`${item.basis_kind}-${item.basis_ref}-${i}`}>
                  <div className="item-no">{i + 1}</div>
                  <div>
                    <div className="row gap">
                      <Badge tone="amber">{pretty(item.basis_kind)}</Badge>
                      {item.rule_section && (
                        <span>
                          Rule 21 §{item.rule_section}
                          {item.rule_sheet ? ` · Sheet ${item.rule_sheet}` : ""}
                        </span>
                      )}
                    </div>
                    <h3>{item.description}</h3>
                    {item.basis_kind === "missing_document" ? (
                      <div className="missing">
                        <X size={16} /> {pretty(item.basis_ref)} — Not submitted
                      </div>
                    ) : item.basis_kind === "screen" ? (
                      <button className="text-link" onClick={() => onScreen(item.basis_ref)}>
                        Open Screen {item.basis_ref}
                      </button>
                    ) : evidence.length > 0 ? (
                      <div className="evidence-links">
                        {evidence.map((f) => (
                          <button key={f.id} onClick={() => onFact(f)}>
                            <FileText size={15} />
                            {pretty(f.document_kind)} · page {f.page_no}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <p className="muted">No document page recorded for this item.</p>
                    )}
                  </div>
                </article>
              );
            })}
          </div>
        </Panel>
      )}
    </>
  );
}

function ScreenDetails({ s }: { s: Screen }) {
  return (
    <details id={`screen-${s.screen}`} className="screen">
      <summary>
        <span className="screen-id">{s.screen}</span>
        <span className="screen-reason">{s.reason ?? "No reason recorded"}</span>
        <ScreenBadge status={s.status} />
        <ChevronDown size={16} />
      </summary>
      <div className="screen-body">
        {s.synthetic_inputs.length > 0 && <TrustTag kind="synthetic" />}
        <dl>
          <div>
            <dt>Formula</dt>
            <dd>{s.formula ?? "Not applicable"}</dd>
          </div>
          <div>
            <dt>Computed / threshold</dt>
            <dd>
              {s.computed ?? "—"} / {s.threshold ?? "—"}
            </dd>
          </div>
          {Object.keys(s.inputs).length > 0 && (
            <div>
              <dt>Inputs</dt>
              <dd>
                {Object.entries(s.inputs).map(([k, v]) => (
                  <code key={k}>
                    {k}: {v}
                  </code>
                ))}
              </dd>
            </div>
          )}
          {s.missing_inputs.length > 0 && (
            <div>
              <dt>Missing ({s.blocker ?? "unknown"} to supply)</dt>
              <dd>{s.missing_inputs.join(", ")}</dd>
            </div>
          )}
          {s.routed_by && (
            <div>
              <dt>Routed by</dt>
              <dd>Screen {s.routed_by}</dd>
            </div>
          )}
          <div>
            <dt>Citations</dt>
            <dd>
              {s.citations.map((c, i) => (
                <span key={i}>
                  §{c.section} · Sheet {c.sheet}
                  {c.quote && <blockquote>{c.quote}</blockquote>}
                  {c.interpretation && <em className="muted"> Interpretation: {c.interpretation}</em>}
                </span>
              ))}
            </dd>
          </div>
        </dl>
      </div>
    </details>
  );
}

function DecisionPanel({ proposal, onDecided }: { proposal: Proposal; onDecided: (p: Proposal) => void }) {
  const [reviewer, setReviewer] = useState("");
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [letter, setLetter] = useState(proposal.letter_md);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const diff = useMemo(() => (editing ? lineDiff(proposal.letter_md, letter) : []), [editing, letter, proposal.letter_md]);
  const changed = letter !== proposal.letter_md;

  if (proposal.status !== "pending_review") {
    return (
      <Panel title="Engineer decision">
        <div className="locked">
          <Check size={18} />
          <strong>{pretty(proposal.status)}</strong>
          <span>
            by {proposal.reviewed_by}
            {proposal.reviewed_at ? ` · ${new Date(proposal.reviewed_at).toLocaleString()}` : ""}
          </span>
          {proposal.review_note && <p>{proposal.review_note}</p>}
        </div>
        <p className="muted">Reviewed drafts are locked by the database.</p>
      </Panel>
    );
  }

  const submit = async (action: "approve" | "edit" | "reject") => {
    setError("");
    setBusy(true);
    try {
      onDecided(await decide(proposal.id, { action, reviewer, note, letter_md: action === "edit" ? letter : null }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <Panel title="Engineer decision">
      <p className="muted">Nothing is sent without a named engineer.</p>
      <Field label="Engineer name">
        <input value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Required" />
      </Field>
      <Field label="Decision note">
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} />
      </Field>
      {editing && (
        <>
          <Field label="Revised letter">
            <textarea className="letter-edit" value={letter} onChange={(e) => setLetter(e.target.value)} />
          </Field>
          <details className="diff" open={changed}>
            <summary>Changes against the draft</summary>
            <pre>
              {!changed
                ? "No changes yet."
                : diff
                    .filter((d) => d.kind !== " ")
                    .map((d, i) => (
                      <span key={i} style={{ display: "block", color: d.kind === "+" ? "var(--success, #15803d)" : "var(--danger, #b91c1c)" }}>
                        {d.kind} {d.line}
                      </span>
                    ))}
            </pre>
          </details>
        </>
      )}
      {error && <div className="error-box">{error}</div>}
      <div className="decision-actions">
        {editing ? (
          <Button disabled={busy || !reviewer.trim() || !changed} onClick={() => submit("edit")}>
            Save edited letter
          </Button>
        ) : (
          <Button disabled={busy || !reviewer.trim()} onClick={() => submit("approve")}>
            Approve as drafted
          </Button>
        )}
        <Button
          variant="secondary"
          disabled={busy}
          onClick={() => {
            setEditing(!editing);
            setLetter(proposal.letter_md);
          }}
        >
          {editing ? "Cancel edit" : "Edit letter"}
        </Button>
        <Button variant="danger" disabled={busy || !reviewer.trim()} onClick={() => submit("reject")}>
          Reject
        </Button>
      </div>
    </Panel>
  );
}
