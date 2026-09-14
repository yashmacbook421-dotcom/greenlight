"use client";

import { useMemo, useState } from "react";
import { Search, SlidersHorizontal, Sparkles } from "lucide-react";
import type { DefectFamily, QueueCase } from "@/lib/types";
import { createDemoPacket, listCases, runReview } from "@/lib/api";
import { AppLink, useAppNavigate } from "@/components/app-link";
import { Badge, Button, Panel } from "@/components/ui";
import { DispositionBadge } from "@/components/status";
export function QueuePage({
  initial,
  families,
}: {
  initial: QueueCase[];
  families: DefectFamily[];
}) {
  const [cases, setCases] = useState(initial);
  const [q, setQ] = useState("");
  const [showEval, setShowEval] = useState(false);
  const [status, setStatus] = useState("all");
  const [family, setFamily] = useState("applicant_conflict");
  const [oracle, setOracle] = useState(true);
  const [llm, setLlm] = useState(false);
  const [error, setError] = useState("");
  const [creating, setCreating] = useState(false);
  const [running, setRunning] = useState<string | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [demo, setDemo] = useState(false);
  const navigate = useAppNavigate();
  const filtered = useMemo(
    () =>
      cases
        .filter(
          (c) =>
            (showEval || !(c.submitter ?? "").startsWith("[eval")) &&
            (status === "all" || c.status === status) &&
            `${c.applicant_name ?? ""} ${c.site_address ?? ""} ${c.submitter ?? ""}`
              .toLowerCase()
              .includes(q.toLowerCase()),
        )
        .sort(
          (a, b) => (b.proposal?.guardrail_failures ?? 0) - (a.proposal?.guardrail_failures ?? 0),
        ),
    [cases, q, showEval, status],
  );
  const run = async (id: string) => {
    setRunning(id);
    setElapsed(0);
    const timer = setInterval(() => setElapsed((e) => e + 1), 1000);
    setError("");
    try {
      await runReview(id, llm);
      navigate(`/review/${id}`);
    } catch (e) {
      setError(`Review failed: ${e instanceof Error ? e.message : "unknown error"}`);
      setCases(await listCases().catch(() => cases));
    } finally {
      clearInterval(timer);
      setRunning(null);
    }
  };
  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">INTERCONNECTION OPERATIONS</div>
          <h1>Review queue</h1>
          <p>Applications waiting for an engineer’s attention.</p>
        </div>
        <Button onClick={() => setDemo(true)}>
          <Sparkles size={16} />
          Add demo application
        </Button>
      </header>
      <div className="queue-toolbar">
        <div className="search-box">
          <Search size={17} />
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search applicant, site or submitter"
          />
        </div>
        <label>
          <SlidersHorizontal size={16} />
          <select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="all">All statuses</option>
            <option value="received">Ready to run</option>
            <option value="pending_review">Needs review</option>
            <option value="closed">Closed</option>
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={showEval}
            onChange={(e) => setShowEval(e.target.checked)}
          />{" "}
          Show eval cases
        </label>
      </div>
      <div className="queue-summary">
        <span>
          <strong>{filtered.length}</strong> visible applications
        </span>
        <span>
          <strong>{filtered.filter((c) => c.proposal?.guardrail_failures).length}</strong> code
          checks need attention
        </span>
        <label className="check">
          <input type="checkbox" checked={llm} onChange={(e) => setLlm(e.target.checked)} /> Use
          Claude when reviewing <small>Typically $0.15–$0.40</small>
        </label>
      </div>
      {error && <div className="error-box">{error}</div>}
      <Panel className="queue-panel">
        <div className="case-table">
          <div className="case-row case-header">
            <span>Applicant / site</span>
            <span>Received</span>
            <span>Draft outcome</span>
            <span>Checks</span>
            <span>Status</span>
            <span></span>
          </div>
          {filtered.map((c) => (
            <div className="case-row" key={c.case_id}>
              <span className="case-person">
                <strong>{c.applicant_name ?? "Applicant not provided"}</strong>
                <small>{c.site_address ?? "Site not provided"}</small>
                <small>{c.submitter ?? "Submitter not provided"}</small>
              </span>
              <span>
                {new Date(c.received_at).toLocaleDateString()}
                <small>{c.documents} document{c.documents === 1 ? "" : "s"}</small>
              </span>
              <span>
                {c.proposal ? (
                  <DispositionBadge value={c.proposal.disposition} />
                ) : (
                  <span className="muted">Not reviewed</span>
                )}
              </span>
              <span>
                {c.proposal?.guardrail_failures ? (
                  <Badge tone="red">{c.proposal.guardrail_failures} flagged</Badge>
                ) : c.proposal ? (
                  <Badge tone="green">Passed</Badge>
                ) : (
                  "—"
                )}
              </span>
              <span>
                <Badge tone={c.status === "pending_review" ? "blue" : "neutral"}>
                  {c.status.replaceAll("_", " ")}
                </Badge>
              </span>
              <span>
                {c.proposal ? (
                  <AppLink to={`/review/${c.case_id}`} className="button-link">
                    Open review
                  </AppLink>
                ) : (
                  <Button disabled={running !== null} onClick={() => run(c.case_id)}>
                    {running === c.case_id ? `${elapsed}s · Reviewing…` : "Run review"}
                  </Button>
                )}
              </span>
            </div>
          ))}
        </div>
      </Panel>
      {demo && (
        <div className="modal-backdrop">
          <div className="modal">
            <h2>Add demo application</h2>
            <p>Choose a known packet pattern to test the review flow.</p>
            <label>
              Defect family
              <select value={family} onChange={(e) => setFamily(e.target.value)}>
                {families.map((f) => (
                  <option key={f.name} value={f.name}>
                    {f.name.replaceAll("_", " ")}
                  </option>
                ))}
              </select>
            </label>
            <p className="family-note">{families.find((f) => f.name === family)?.description}</p>
            <label className="check">
              <input
                type="checkbox"
                checked={oracle}
                onChange={(e) => setOracle(e.target.checked)}
              />{" "}
              Use oracle facts
            </label>
            <div className="modal-actions">
              <Button variant="secondary" onClick={() => setDemo(false)}>
                Cancel
              </Button>
              <Button
                disabled={creating}
                onClick={async () => {
                  setCreating(true);
                  setError("");
                  try {
                    // A fresh seed each time, so two demos of the same family are different applications.
                    await createDemoPacket({ family, seed: Math.floor(Math.random() * 100000), oracle_facts: oracle });
                    setCases(await listCases());
                    setDemo(false);
                  } catch (e) {
                    setError(`Could not create demo application: ${e instanceof Error ? e.message : "unknown error"}`);
                    setDemo(false);
                  } finally {
                    setCreating(false);
                  }
                }}
              >
                {creating ? "Creating…" : "Create packet"}
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
