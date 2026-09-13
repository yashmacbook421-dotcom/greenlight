"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type EvalRunDetail, type EvalSummary } from "@/lib/api";

const DISPOSITIONS = ["INITIAL_REVIEW_PASS", "DEFICIENCY_NOTICE", "SUPPLEMENTAL_REVIEW_REQUIRED", "NEEDS_ENGINEER_DETERMINATION"];
const SHORT: Record<string, string> = {
  INITIAL_REVIEW_PASS: "Pass", DEFICIENCY_NOTICE: "Deficiency", SUPPLEMENTAL_REVIEW_REQUIRED: "Supplemental",
  NEEDS_ENGINEER_DETERMINATION: "Engineer",
};

const pct = (x: number | null | undefined) => (x == null ? "—" : `${(x * 100).toFixed(x === 1 ? 0 : 1)}%`);

export default function EvalsPage() {
  const [runs, setRuns] = useState<EvalSummary[] | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<EvalRunDetail | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<EvalSummary[]>("/evals")
      .then((rs) => {
        setRuns(rs);
        const firstUseful = rs.find((r) => r.status === "completed" && (r.packets ?? 0) > 0);
        if (firstUseful) setSelected(firstUseful.id);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  useEffect(() => {
    if (!selected) return;
    api<EvalRunDetail>(`/evals/${selected}`).then(setDetail).catch((e: Error) => setError(e.message));
  }, [selected]);

  if (error) return <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>;

  const m = detail?.metrics;
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Evals</h1>
        <p className="max-w-3xl text-sm text-slate-600">
          Generated application packets with injected defects and known ground truth. <b>Oracle</b> runs feed the
          generator&apos;s exact facts and measure everything after extraction; <b>live</b> runs call Claude end to end and
          add extraction accuracy and cost. Run with <code className="text-xs">python -m scripts.run_eval</code>.
        </p>
      </div>

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr><th className="px-4 py-2">Run</th><th className="px-4 py-2">Mode</th><th className="px-4 py-2">Packets</th>
              <th className="px-4 py-2">Disposition acc.</th><th className="px-4 py-2">Detection P / R</th><th className="px-4 py-2">Cost / app</th><th /></tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {runs?.map((r) => (
              <tr key={r.id} className={r.id === selected ? "bg-emerald-50/50" : ""}>
                <td className="px-4 py-2"><div className="text-slate-800">{r.note ?? r.id.slice(0, 8)}</div>
                  <div className="text-xs text-slate-500">{new Date(r.started_at).toLocaleString()} · {r.status}</div></td>
                <td className="px-4 py-2"><span className={`rounded px-1.5 py-0.5 text-xs font-medium ${r.mode === "live" ? "bg-indigo-50 text-indigo-800" : "bg-slate-100 text-slate-700"}`}>{r.mode}</span></td>
                <td className="px-4 py-2">{r.packets ?? "—"}</td>
                <td className="px-4 py-2">{pct(r.disposition_accuracy)}</td>
                <td className="px-4 py-2">{pct(r.detection?.precision)} / {pct(r.detection?.recall)}</td>
                <td className="px-4 py-2">{r.cost_usd?.per_application_mean ? `$${Number(r.cost_usd.per_application_mean).toFixed(3)}` : "—"}</td>
                <td className="px-4 py-2 text-right"><button onClick={() => setSelected(r.id)} className="text-xs font-medium text-emerald-700 hover:text-emerald-900">details</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {m && detail && (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
            <Tile label="Disposition accuracy" value={pct(m.disposition_accuracy)} sub={`${m.packets} packets, ${m.errors} errors`} />
            <Tile label="Detection precision" value={pct(m.detection?.precision)} sub={`${m.detection?.false_positives} false positives`} />
            <Tile label="Detection recall" value={pct(m.detection?.recall)} sub={`${m.detection?.true_positives} detected`} />
            <Tile label="Deterministic screens" value={pct(m.determinism_pass_rate)} sub="same input → same result" />
            {m.extraction && <Tile label="Extraction recall / precision" value={`${pct(m.extraction.recall_mean)} / ${pct(m.extraction.precision_mean)}`} sub="vs labelled facts" />}
            {m.cost_usd && <Tile label="Cost per application" value={`$${Number(m.cost_usd.per_application_mean).toFixed(3)}`} sub={`max $${Number(m.cost_usd.per_application_max).toFixed(3)} · ${m.llm_calls_mean} calls`} />}
            <Tile label="Latency" value={`${m.latency_s?.mean ?? "—"} s`} sub={`max ${m.latency_s?.max ?? "—"} s`} />
          </div>

          <div className="grid gap-5 lg:grid-cols-2">
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold">Disposition confusion matrix</h2>
              <table className="text-sm">
                <thead><tr><th className="px-2 py-1 text-left text-xs text-slate-500">expected ↓ / proposed →</th>
                  {DISPOSITIONS.map((d) => <th key={d} className="px-2 py-1 text-xs text-slate-500">{SHORT[d]}</th>)}</tr></thead>
                <tbody>
                  {DISPOSITIONS.map((exp) => (
                    <tr key={exp}>
                      <td className="px-2 py-1 text-xs text-slate-600">{SHORT[exp]}</td>
                      {DISPOSITIONS.map((got) => {
                        const n = m.confusion?.[exp]?.[got] ?? 0;
                        const tone = n === 0 ? "text-slate-300" : exp === got ? "bg-emerald-100 font-semibold text-emerald-900" : "bg-rose-100 font-semibold text-rose-900";
                        return <td key={got} className={`px-2 py-1 text-center ${tone}`}>{n}</td>;
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
            <section className="rounded-lg border border-slate-200 bg-white p-4">
              <h2 className="mb-3 text-sm font-semibold">How often code had to flag or overrule the draft</h2>
              <ul className="space-y-1.5 text-sm">
                {Object.entries(m.guardrail_failure_rates ?? {}).map(([k, v]) => (
                  <li key={k} className="flex justify-between"><span className="text-slate-600">{k.replaceAll("_", " ")}</span><b>{pct(v as number)}</b></li>
                ))}
              </ul>
            </section>
          </div>

          <section className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">By defect family</h2>
            <table className="min-w-full text-sm">
              <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
                <tr><th className="px-4 py-2">Family</th><th className="px-4 py-2">Packets</th><th className="px-4 py-2">Disposition acc.</th>
                  <th className="px-4 py-2">Detection recall</th><th className="px-4 py-2">Spurious</th><th className="px-4 py-2">Entailed</th></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {Object.entries(m.families ?? {}).map(([name, f]) => {
                  const fam = f as { packets: number; disposition_accuracy: number; detection_recall: number | null; spurious_signals: number; consequential_signals?: number };
                  return (
                    <tr key={name}>
                      <td className="px-4 py-2 font-mono text-xs">{name}</td><td className="px-4 py-2">{fam.packets}</td>
                      <td className="px-4 py-2">{pct(fam.disposition_accuracy)}</td><td className="px-4 py-2">{fam.detection_recall == null ? "n/a" : pct(fam.detection_recall)}</td>
                      <td className={`px-4 py-2 ${fam.spurious_signals ? "font-semibold text-rose-700" : ""}`}>{fam.spurious_signals}</td>
                      <td className="px-4 py-2 text-slate-500">{fam.consequential_signals ?? 0}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>

          <section className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
            <h2 className="border-b border-slate-100 px-4 py-2.5 text-sm font-semibold">Packets</h2>
            <table className="min-w-full text-xs">
              <thead className="bg-slate-50 text-left uppercase tracking-wide text-slate-500">
                <tr><th className="px-4 py-2">Packet</th><th className="px-4 py-2">Expected</th><th className="px-4 py-2">Proposed</th>
                  <th className="px-4 py-2">Guardrail flags</th><th className="px-4 py-2">Cost</th><th className="px-4 py-2">Latency</th><th /></tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {detail.packets.map((p) => (
                  <tr key={p.packet_id} className={p.error ? "bg-rose-50" : p.correct ? "" : "bg-amber-50"}>
                    <td className="px-4 py-1.5 font-mono">{p.packet_id}</td>
                    <td className="px-4 py-1.5">{SHORT[p.expected_disposition] ?? "—"}</td>
                    <td className="px-4 py-1.5">{p.error ? <span className="text-rose-700">{p.error}</span> : `${SHORT[p.disposition]}${p.correct ? "" : " ✕"}`}</td>
                    <td className="px-4 py-1.5">{p.guardrails ? Object.entries(p.guardrails).filter(([, ok]) => !ok).map(([k]) => k).join(", ") || "—" : "—"}</td>
                    <td className="px-4 py-1.5">{p.cost_usd && Number(p.cost_usd) > 0 ? `$${Number(p.cost_usd).toFixed(3)}` : "—"}</td>
                    <td className="px-4 py-1.5">{p.latency_s ?? "—"} s</td>
                    <td className="px-4 py-1.5 text-right">{p.case_id && <Link href={`/review/${p.case_id}`} className="text-emerald-700 hover:text-emerald-900">review →</Link>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </div>
      )}
    </div>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-0.5 text-xl font-semibold tracking-tight">{value}</div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}
