"use client";

import type { TraceRun } from "@/lib/types";
import { Badge, Panel } from "@/components/ui";
import { AppLink } from "@/components/app-link";
export function TracePage({ runs, caseId }: { runs: TraceRun[]; caseId: string }) {
  const run = runs[0];
  if (!run)
    return (
      <div className="page">
        <h1>No agent trace</h1>
        <p>This review used the deterministic template.</p>
      </div>
    );
  return (
    <div className="page">
      <div className="breadcrumbs">
        <AppLink to={`/review/${caseId}`}>Review</AppLink>
        <span>/</span>
        <span>Agent trace</span>
      </div>
      <header className="page-head">
        <div>
          <div className="eyebrow">READABLE AI REPLAY</div>
          <h1>Agent trace</h1>
          <p>What the model examined, which tools it used, and what it cost.</p>
        </div>
        <Badge tone="blue">{run.model}</Badge>
      </header>
      <div className="metric-grid">
        <Panel>
          <strong>
            {run.steps_used} / {run.step_budget}
          </strong>
          <span>Calls used / budget</span>
        </Panel>
        <Panel>
          <strong>${Number(run.cost_usd).toFixed(4)}</strong>
          <span>Cost / ${run.cost_ceiling_usd} ceiling</span>
        </Panel>
        <Panel>
          <strong>
            {run.ended_at
              ? `${Math.round((new Date(run.ended_at).getTime() - new Date(run.started_at).getTime()) / 1000)}s`
              : "Running"}
          </strong>
          <span>Total elapsed</span>
        </Panel>
        <Panel>
          <strong>{run.terminated_by}</strong>
          <span>How it ended</span>
        </Panel>
      </div>
      <div className="timeline">
        {run.steps.map((step) => (
          <details className="trace-step" key={step.n}>
            <summary>
              <span className="step-no">{step.n}</span>
              <div>
                <strong>{step.tool ?? "Claude reasoning"}</strong>
                <small>
                  {step.role}
                  {step.latency_ms != null && ` · ${step.latency_ms.toLocaleString()} ms`}
                </small>
              </div>
              <div className="trace-cost">{step.cost_usd ? `$${step.cost_usd}` : "tool call"}</div>
            </summary>
            <div className="trace-body">
              <div>
                <h4>Input</h4>
                <pre>
                  {JSON.stringify(step.args ?? { input_tokens: step.input_tokens }, null, 2)}
                </pre>
              </div>
              <div>
                <h4>Result</h4>
                <pre>{JSON.stringify(step.result, null, 2)}</pre>
              </div>
            </div>
          </details>
        ))}
      </div>
    </div>
  );
}
