"use client";

import type { EvalDetail, EvalRun } from "@/lib/types";
import { Badge, Panel } from "@/components/ui";
import { AppLink } from "@/components/app-link";

const pct = (n: number | null | undefined) => (n == null ? "—" : `${Math.round(n * 1000) / 10}%`);
const DISPOSITIONS = [
  ["INITIAL_REVIEW_PASS", "Pass"],
  ["DEFICIENCY_NOTICE", "Deficiency"],
  ["SUPPLEMENTAL_REVIEW_REQUIRED", "Supplemental"],
  ["NEEDS_ENGINEER_DETERMINATION", "Engineer"],
] as const;

type Family = {
  packets: number;
  disposition_accuracy: number;
  detection_recall: number | null;
  spurious_signals: number;
  consequential_signals?: number;
};

export function EvalsPage({
  runs,
  details,
  selectedId,
  loadingDetail,
  detailError,
  onSelect,
}: {
  runs: EvalRun[];
  details: EvalDetail | null;
  selectedId: string;
  loadingDetail: boolean;
  detailError: string;
  onSelect: (id: string) => void;
}) {
  const m = details?.metrics ?? {};
  const confusion = m["confusion"] as Record<string, Record<string, number>> | undefined;
  const failureRates = m["guardrail_failure_rates"] as Record<string, number | null> | undefined;
  const families = m["families"] as Record<string, Family> | undefined;
  const costShare = m["cost_share_by_stage"] as Record<string, number> | undefined;
  const cost = m["cost_usd"] as { total: string; per_application_mean: string | null } | undefined;
  const hasPackets = (m["packets"] ?? 0) > 0 && (m["errors"] ?? 0) < (m["packets"] ?? 0);

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">QUALITY & COST</div>
          <h1>Evaluations</h1>
          <p>
            <strong>Oracle</strong> runs feed known facts to test the deterministic pipeline;{" "}
            <strong>live</strong> runs call Claude end to end and add extraction accuracy and cost.
          </p>
        </div>
      </header>
      <div className="eval-layout">
        <aside className="run-list">
          {runs.map((r) => (
            <button className={selectedId === r.id ? "active" : ""} onClick={() => onSelect(r.id)} key={r.id}>
              <div>
                <Badge tone={r.mode === "live" ? "blue" : "neutral"}>{r.mode}</Badge>
                <Badge tone={r.status === "completed" ? "green" : r.status === "failed" ? "red" : "amber"}>
                  {r.status}
                </Badge>
              </div>
              <strong>{r.note ?? r.id.slice(0, 8)}</strong>
              <small>
                {r.packets ?? 0} packets · {new Date(r.started_at).toLocaleDateString()}
              </small>
            </button>
          ))}
        </aside>
        <div className="eval-detail" aria-busy={loadingDetail}>
          {detailError && <div className="error-box">{detailError}</div>}
          {loadingDetail && <p className="muted">Loading run…</p>}
          {details && !loadingDetail && !hasPackets && (
            <Panel title="No results for this run">
              <p className="muted">
                {details.status === "failed"
                  ? "Every packet in this run errored, so there are no metrics. Open a packet below to see the error."
                  : "This run has no completed packets."}
              </p>
            </Panel>
          )}
          {details && !loadingDetail && (
            <>
              {hasPackets && (
                <>
                  <div className="metric-grid">
                    <Panel>
                      <strong>{pct(m["disposition_accuracy"])}</strong>
                      <span>Disposition accuracy</span>
                    </Panel>
                    <Panel>
                      <strong>{pct(m["detection"]?.recall)}</strong>
                      <span>Detection recall</span>
                    </Panel>
                    <Panel>
                      <strong>{pct(m["detection"]?.precision)}</strong>
                      <span>Detection precision</span>
                    </Panel>
                    <Panel>
                      <strong>{cost?.per_application_mean ? `$${Number(cost.per_application_mean).toFixed(3)}` : "$0"}</strong>
                      <span>{details.mode === "live" ? "Cost per application" : "No model calls (oracle)"}</span>
                    </Panel>
                  </div>
                  <Panel title="Expected vs proposed outcome">
                    <div className="matrix" role="table" aria-label="Rows are expected outcomes, columns are proposed outcomes">
                      <div></div>
                      {DISPOSITIONS.map(([d, label]) => (
                        <small key={d}>{label}</small>
                      ))}
                      {DISPOSITIONS.map(([expected, label]) => (
                        <div className="contents" key={expected}>
                          <strong>{label}</strong>
                          {DISPOSITIONS.map(([proposed]) => {
                            const value = confusion?.[expected]?.[proposed] ?? 0;
                            return (
                              <span
                                className={value ? "hit" : ""}
                                key={`${expected}-${proposed}`}
                                title={`${value} expected ${expected.toLowerCase()}, proposed ${proposed.toLowerCase()}`}
                              >
                                {value}
                                {value > 0 && expected !== proposed ? " ✕" : ""}
                              </span>
                            );
                          })}
                        </div>
                      ))}
                    </div>
                  </Panel>
                  <Panel title="When code intervened">
                    <div className="rates">
                      {Object.entries(failureRates ?? {}).map(([name, value]) => (
                        <div key={name}>
                          <span>{name.replaceAll("_", " ")}</span>
                          <strong>{pct(value)}</strong>
                          <div>
                            <i style={{ width: `${(value ?? 0) * 100}%` }} />
                          </div>
                        </div>
                      ))}
                    </div>
                  </Panel>
                  {families && (
                    <Panel title="By defect family">
                      <div className="packet-table">
                        {Object.entries(families).map(([name, f]) => (
                          <div key={name}>
                            <span>
                              <strong>{name.replaceAll("_", " ")}</strong>
                              <small>{f.packets} packets</small>
                            </span>
                            <span>Outcome {pct(f.disposition_accuracy)}</span>
                            <span>Detection {f.detection_recall == null ? "n/a" : pct(f.detection_recall)}</span>
                            <Badge tone={f.spurious_signals ? "red" : "green"}>{f.spurious_signals} spurious</Badge>
                          </div>
                        ))}
                      </div>
                    </Panel>
                  )}
                  {costShare && Object.keys(costShare).length > 0 && (
                    <Panel title="Where the money goes">
                      <div className="rates">
                        {Object.entries(costShare).map(([stage, share]) => (
                          <div key={stage}>
                            <span>{stage.replaceAll("_", " ")}</span>
                            <strong>{pct(share)}</strong>
                            <div>
                              <i style={{ width: `${share * 100}%` }} />
                            </div>
                          </div>
                        ))}
                      </div>
                    </Panel>
                  )}
                </>
              )}
              <Panel title="Packet results">
                <div className="packet-table">
                  {details.packets.map((p) => {
                    const failed = "error" in p;
                    return (
                      <div key={p.packet_id}>
                        <span>
                          <strong>{p.family.replaceAll("_", " ")}</strong>
                          <small>{p.packet_id}</small>
                        </span>
                        {failed ? (
                          <Badge tone="red">Error</Badge>
                        ) : (
                          <Badge tone={p.correct ? "green" : "red"}>{p.correct ? "Correct" : "Incorrect"}</Badge>
                        )}
                        <span>{failed ? String((p as { error?: string }).error).slice(0, 80) : `${p.latency_s}s`}</span>
                        <span>{!failed && Number(p.cost_usd) > 0 ? `$${Number(p.cost_usd).toFixed(4)}` : "—"}</span>
                        {p.case_id ? <AppLink to={`/review/${p.case_id}`}>Open review</AppLink> : <span />}
                      </div>
                    );
                  })}
                </div>
              </Panel>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
