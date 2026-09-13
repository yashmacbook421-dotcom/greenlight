"use client";

import Link from "next/link";
import { use, useEffect, useState } from "react";

import { api, type TraceRun } from "@/lib/api";

type Block = { type: string; text?: string; name?: string; input?: unknown };

export default function TracePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [runs, setRuns] = useState<TraceRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<TraceRun[]>(`/cases/${id}/trace`).then(setRuns).catch((e: Error) => setError(e.message));
  }, [id]);

  if (error) return <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>;
  if (!runs) return <p className="text-sm text-slate-500">Loading trace…</p>;

  return (
    <div className="space-y-5">
      <div>
        <Link href={`/review/${id}`} className="text-xs text-slate-500 hover:text-slate-800">← Review</Link>
        <h1 className="mt-1 text-xl font-semibold tracking-tight">Agent trace</h1>
        <p className="text-sm text-slate-600">Every model call and tool execution, as recorded. Replayable after the fact.</p>
      </div>
      {runs.length === 0 && <p className="text-sm text-slate-500">No agent runs for this case (the draft came from the template).</p>}
      {runs.map((run) => (
        <section key={run.id} className="rounded-lg border border-slate-200 bg-white">
          <div className="grid grid-cols-2 gap-4 border-b border-slate-100 px-4 py-3 text-sm sm:grid-cols-5">
            <Stat label="Model" value={run.model} />
            <Stat label="Ended by" value={run.terminated_by ?? "running"} />
            <Stat label="Model calls" value={`${run.steps_used} / ${run.step_budget}`} />
            <Stat label="Cost" value={`$${Number(run.cost_usd).toFixed(4)} / $${Number(run.cost_ceiling_usd).toFixed(2)}`} />
            <Stat label="Started" value={new Date(run.started_at).toLocaleString()} />
          </div>
          <ol className="divide-y divide-slate-100">
            {run.steps.map((step) => (
              <li key={step.n} className="px-4 py-3 text-sm">
                <div className="flex flex-wrap items-center gap-3 text-xs text-slate-500">
                  <span className="font-mono">#{step.n}</span>
                  <span className={`rounded px-1.5 py-0.5 font-medium ${step.role === "assistant" ? "bg-indigo-50 text-indigo-800" : "bg-emerald-50 text-emerald-800"}`}>
                    {step.role === "assistant" ? "model" : `tool · ${step.tool}`}
                  </span>
                  {step.input_tokens != null && <span>{step.input_tokens.toLocaleString()} in / {step.output_tokens?.toLocaleString()} out</span>}
                  {step.cost_usd && <span>${Number(step.cost_usd).toFixed(4)}</span>}
                  {step.latency_ms != null && <span>{(step.latency_ms / 1000).toFixed(1)} s</span>}
                </div>
                {step.role === "assistant" ? <AssistantTurn result={step.result as { content?: Block[]; stop_reason?: string }} />
                  : <ToolCall args={step.args} result={step.result} />}
              </li>
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}

function AssistantTurn({ result }: { result: { content?: Block[]; stop_reason?: string } }) {
  const blocks = result?.content ?? [];
  return (
    <div className="mt-2 space-y-1.5">
      {blocks.map((b, i) => {
        if (b.type === "text" && b.text) return <p key={i} className="whitespace-pre-wrap text-slate-800">{b.text}</p>;
        if (b.type === "tool_use") return <p key={i} className="font-mono text-xs text-slate-600">→ calls <b>{b.name}</b></p>;
        if (b.type === "thinking") return <p key={i} className="text-xs italic text-slate-400">(thinking)</p>;
        return null;
      })}
      <p className="text-[11px] text-slate-400">stop: {result?.stop_reason}</p>
    </div>
  );
}

function ToolCall({ args, result }: { args: unknown; result: unknown }) {
  const [open, setOpen] = useState(false);
  const r = result as { is_error?: boolean } | null;
  return (
    <div className="mt-2 space-y-1">
      <pre className="overflow-x-auto rounded bg-slate-50 px-2 py-1.5 text-xs text-slate-700">{JSON.stringify(args, null, 1)}</pre>
      <button onClick={() => setOpen(!open)} className={`text-xs font-medium ${r?.is_error ? "text-rose-700" : "text-slate-500"} hover:text-slate-900`}>
        {open ? "hide result" : r?.is_error ? "show error result" : "show result"}
      </button>
      {open && <pre className="max-h-96 overflow-auto rounded bg-slate-900 px-2 py-1.5 text-xs text-slate-100">{JSON.stringify(result, null, 1)}</pre>}
    </div>
  );
}
