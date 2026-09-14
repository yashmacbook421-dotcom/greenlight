"use client";

import { ArrowRight, Bot, Calculator, FileSearch, ShieldCheck, UserCheck } from "lucide-react";
import type { EvalRun } from "@/lib/types";
import { Badge, Panel } from "@/components/ui";
const stages = [
  "Intake",
  "Extraction",
  "Reconciliation",
  "Screens",
  "Agent",
  "Guardrails",
  "Engineer",
];
const pct = (n: number | null | undefined) => (n == null ? "—" : `${Math.round(n * 1000) / 10}%`);
const MEANS: Record<string, string> = {
  oracle: "Known facts fed in: measures the deterministic pipeline, not the AI.",
  live: "Claude end to end: extraction, judgment and drafting.",
};

export function AboutPage({ runs = [] }: { runs?: EvalRun[] }) {
  const latest = (["oracle", "live"] as const)
    .map((mode) => runs.find((r) => r.mode === mode && r.status === "completed" && (r.packets ?? 0) > 0))
    .filter((r): r is EvalRun => Boolean(r));
  return (
    <div className="page about">
      <header className="about-hero">
        <Badge tone="green">TRUSTWORTHY AUTOMATION FOR REGULATED WORK</Badge>
        <h1>Greenlight</h1>
        <p>AI prepares the review. Code proves the boundaries. An engineer holds authority.</p>
      </header>
      <section className="principles">
        <article>
          <Bot />
          <span>AI handles ambiguity</span>
          <p>Reads messy PDFs, reconciles meaning, and drafts the formal letter.</p>
        </article>
        <article>
          <Calculator />
          <span>Code handles arithmetic</span>
          <p>Runs Rule 21 screens and verifies every number and citation.</p>
        </article>
        <article>
          <UserCheck />
          <span>Humans hold authority</span>
          <p>A named engineer approves, edits, or rejects every draft.</p>
        </article>
      </section>
      <Panel title="From packet to accountable decision">
        <div className="pipeline">
          {stages.map((s, i) => (
            <div key={s}>
              <span>{i + 1}</span>
              <strong>{s}</strong>
              {i < stages.length - 1 && <ArrowRight />}
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="The problem">
        <div className="problem">
          <FileSearch />
          <div>
            <h3>Interconnection review is manual, and the queue keeps growing</h3>
            <p>
              Before rooftop solar or a battery can connect in California, the utility reviews a packet of
              installer PDFs against Electric Rule 21, a 290-page tariff. An engineer reads every document,
              checks they agree, runs the technical screens by hand, and writes the letter. Adoption is
              outpacing that review capacity, while the tariff sets deadlines such as 10 business days to
              flag an incomplete request.
            </p>
          </div>
        </div>
      </Panel>
      <div className="about-grid">
        <Panel title="Why it matters">
          <div className="problem">
            <FileSearch />
            <div>
              <h3>Evidence, not guesswork</h3>
              <p>
                Every conclusion sits beside the PDF page, extracted quote, formula, threshold, and
                tariff source behind it.
              </p>
            </div>
          </div>
          <div className="problem">
            <ShieldCheck />
            <div>
              <h3>Automation with hard limits</h3>
              <p>
                The model cannot silently relax an outcome. Deterministic checks can flag or
                overrule its draft.
              </p>
            </div>
          </div>
        </Panel>
        <Panel title="Latest evaluations">
          {latest.length === 0 && <p className="muted">Evaluation data is unavailable.</p>}
          {latest.map((run) => (
            <div className="eval-snapshot" key={run.id}>
              <strong>{pct(run.disposition_accuracy)}</strong>
              <span>Disposition accuracy</span>
              <div>
                <span>
                  {run.packets} packet{run.packets === 1 ? "" : "s"}
                  {(run.packets ?? 0) < 10 ? " · small sample" : ""}
                </span>
                <span>{run.mode}</span>
              </div>
              <p>{MEANS[run.mode]}</p>
            </div>
          ))}
        </Panel>
      </div>
    </div>
  );
}
