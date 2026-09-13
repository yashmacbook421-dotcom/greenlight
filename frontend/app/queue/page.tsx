"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { DispositionBadge, ReviewStatusBadge } from "@/components/badges";
import { api, type QueueRow } from "@/lib/api";

interface Family {
  name: string;
  profile: string;
  expected: string;
  description: string;
}

export default function QueuePage() {
  const [rows, setRows] = useState<QueueRow[] | null>(null);
  const [families, setFamilies] = useState<Family[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [family, setFamily] = useState("clean_residential");
  const [oracle, setOracle] = useState(true);
  const [useLlm, setUseLlm] = useState(false);
  const [showEval, setShowEval] = useState(false);

  const load = useCallback(async () => {
    try {
      setRows(await api<QueueRow[]>("/cases"));
      setError(null);
    } catch (e) {
      setError(`Could not reach the Greenlight API: ${(e as Error).message}`);
    }
  }, []);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- initial fetch of external data
    load();
    api<Family[]>("/evals/families").then(setFamilies).catch(() => {});
  }, [load]);

  async function review(caseId: string) {
    setBusy(caseId);
    try {
      await api(`/cases/${caseId}/review?use_llm=${useLlm}`, { method: "POST" });
      await load();
    } catch (e) {
      setError(`Review failed: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  async function createDemo() {
    setBusy("demo");
    try {
      await api("/demo/packets", {
        method: "POST",
        body: JSON.stringify({ family, seed: Math.floor(Math.random() * 10000), oracle_facts: oracle }),
      });
      await load();
    } catch (e) {
      setError(`Could not create demo packet: ${(e as Error).message}`);
    } finally {
      setBusy(null);
    }
  }

  const isEval = (r: QueueRow) => (r.submitter ?? "").startsWith("[eval");
  const visible = rows?.filter((r) => showEval || !isEval(r));
  const hiddenEval = rows ? rows.length - (visible?.length ?? 0) : 0;
  const pending = visible?.filter((r) => r.proposal?.status === "pending_review").length ?? 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">Review queue</h1>
          <p className="text-sm text-slate-600">
            {visible ? `${visible.length} applications · ${pending} awaiting an engineer` : "Loading…"}
            {hiddenEval > 0 && ` · ${hiddenEval} eval cases hidden`}
          </p>
          <label className="mt-1 flex items-center gap-1.5 text-xs text-slate-600">
            <input type="checkbox" checked={showEval} onChange={(e) => setShowEval(e.target.checked)} />
            show eval-corpus cases
          </label>
        </div>
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white p-3 text-sm">
          <select value={family} onChange={(e) => setFamily(e.target.value)}
                  className="rounded-md border border-slate-300 bg-white px-2 py-1.5">
            {(families.length ? families : [{ name: "clean_residential", description: "", profile: "", expected: "" }]).map((f) => (
              <option key={f.name} value={f.name}>{f.name.replaceAll("_", " ")}</option>
            ))}
          </select>
          <label className="flex items-center gap-1.5 text-slate-700">
            <input type="checkbox" checked={oracle} onChange={(e) => setOracle(e.target.checked)} />
            oracle facts
          </label>
          <button onClick={createDemo} disabled={busy !== null}
                  className="rounded-md bg-slate-900 px-3 py-1.5 font-medium text-white hover:bg-slate-700 disabled:opacity-50">
            {busy === "demo" ? "Creating…" : "Add demo application"}
          </button>
          <span className="h-6 w-px bg-slate-200" />
          <label className="flex items-center gap-1.5 text-slate-700" title="Uses Claude for extraction, materiality and drafting; costs money">
            <input type="checkbox" checked={useLlm} onChange={(e) => setUseLlm(e.target.checked)} />
            use Claude when reviewing
          </label>
        </div>
      </div>

      {families.length > 0 && (
        <p className="text-xs text-slate-500">
          {families.find((f) => f.name === family)?.description} · expected:{" "}
          {families.find((f) => f.name === family)?.expected.replaceAll("_", " ").toLowerCase()}
        </p>
      )}

      {error && <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>}

      <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
        <table className="min-w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wide text-slate-500">
            <tr>
              <th className="px-4 py-2.5">Applicant / site</th>
              <th className="px-4 py-2.5">Submitted by</th>
              <th className="px-4 py-2.5">Received</th>
              <th className="px-4 py-2.5">Docs</th>
              <th className="px-4 py-2.5">Draft disposition</th>
              <th className="px-4 py-2.5">Review</th>
              <th className="px-4 py-2.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {visible?.map((r) => (
              <tr key={r.case_id} className="hover:bg-slate-50/60">
                <td className="px-4 py-3">
                  <div className="font-medium">{r.applicant_name ?? "—"}</div>
                  <div className="text-xs text-slate-500">{r.site_address ?? r.case_id}</div>
                </td>
                <td className="px-4 py-3 text-slate-600">{r.submitter ?? "—"}</td>
                <td className="px-4 py-3 whitespace-nowrap text-slate-600">{new Date(r.received_at).toLocaleString()}</td>
                <td className="px-4 py-3 text-slate-600">{r.documents}</td>
                <td className="px-4 py-3">
                  {r.proposal ? (
                    <div className="flex flex-col items-start gap-1">
                      <DispositionBadge disposition={r.proposal.disposition} />
                      {r.proposal.guardrail_failures > 0 && (
                        <span className="text-xs text-rose-700">{r.proposal.guardrail_failures} guardrail flag(s)</span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400">not reviewed</span>
                  )}
                </td>
                <td className="px-4 py-3">{r.proposal ? <ReviewStatusBadge status={r.proposal.status} /> : null}</td>
                <td className="px-4 py-3 text-right whitespace-nowrap">
                  {r.proposal ? (
                    <Link href={`/review/${r.case_id}`} className="font-medium text-emerald-700 hover:text-emerald-900">
                      Open review →
                    </Link>
                  ) : (
                    <button onClick={() => review(r.case_id)} disabled={busy !== null}
                            className="rounded-md border border-slate-300 px-2.5 py-1 text-xs font-medium hover:bg-slate-100 disabled:opacity-50">
                      {busy === r.case_id ? "Reviewing…" : "Run review"}
                    </button>
                  )}
                </td>
              </tr>
            ))}
            {visible?.length === 0 && (
              <tr><td colSpan={7} className="px-4 py-10 text-center text-slate-500">No applications yet. Add a demo application above.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
