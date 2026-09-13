export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8010";

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail ?? body);
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(res.status, detail);
  }
  return res.json() as Promise<T>;
}

export type Disposition =
  | "DEFICIENCY_NOTICE"
  | "INITIAL_REVIEW_PASS"
  | "SUPPLEMENTAL_REVIEW_REQUIRED"
  | "NEEDS_ENGINEER_DETERMINATION";

export interface Verdict {
  name: string;
  passed: boolean;
  detail: string;
  data: Record<string, unknown>;
}

export interface Item {
  description: string;
  basis_kind: "screen" | "fact" | "discrepancy" | "missing_document";
  basis_ref: string;
  rule_section: string | null;
  rule_sheet: number | null;
}

export interface Proposal {
  id: string;
  disposition: Disposition;
  model_disposition: Disposition | null;
  status: "pending_review" | "approved" | "edited" | "rejected";
  letter_md: string;
  items: Item[];
  guardrail_verdicts: Verdict[];
  agent_run_id: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
}

export interface QueueRow {
  case_id: string;
  status: string;
  submitter: string | null;
  received_at: string;
  applicant_name: string | null;
  site_address: string | null;
  documents: number;
  proposal: { id: string; disposition: Disposition; status: string; guardrail_failures: number } | null;
}

export interface Citation {
  ruleset?: string;
  section: string;
  sheet: number;
  quote?: string;
  interpretation?: string;
}

export interface ScreenRow {
  screen: string;
  status: "PASS" | "FAIL" | "INCONCLUSIVE" | "NOT_APPLICABLE" | "SKIPPED";
  reason: string | null;
  formula: string | null;
  computed: string | null;
  threshold: string | null;
  inputs: Record<string, string>;
  citations: Citation[];
  classification: string | null;
  blocker: string | null;
  routed_by: string | null;
  missing_inputs: string[];
  synthetic_inputs: string[];
  overrides: Record<string, string>;
  input_hash: string;
  engine_version: string;
}

export interface Fact {
  id: string;
  field: string;
  value: string;
  unit: string | null;
  instance: string | null;
  value_as_written: string | null;
  unit_as_written: string | null;
  document_id: string;
  document_kind: string;
  page_no: number;
  quote: string;
  verification: string;
}

export interface ReviewBundle {
  case: { id: string; status: string; submitter: string | null; received_at: string };
  application: { utility: string; applicant_name: string | null; site_address: string | null; circuit_model_id: string | null } | null;
  documents: { id: string; kind: string; filename: string; page_count: number; sha256: string;
    pages: { page_no: number; has_text_layer: boolean; anchor: string }[] }[];
  facts: Fact[];
  discrepancies: { field: string; observed: { value: unknown; sources: { fact_ids: string[]; derivation: string | null }[]; chosen: boolean }[];
    material: boolean | null; method: string | null; rationale: string | null }[];
  screens: ScreenRow[];
  scenarios: ScreenRow[];
  proposal: Proposal | null;
}

export interface TraceRun {
  id: string;
  model: string;
  step_budget: number;
  steps_used: number;
  cost_ceiling_usd: string;
  cost_usd: string;
  terminated_by: string | null;
  started_at: string;
  ended_at: string | null;
  steps: { n: number; role: string; tool: string | null; args: Record<string, unknown> | null; result: unknown;
    input_tokens: number | null; output_tokens: number | null; cost_usd: string | null; latency_ms: number | null }[];
}

export interface EvalSummary {
  id: string;
  mode: "oracle" | "live";
  status: string;
  note: string | null;
  started_at: string;
  finished_at: string | null;
  packets: number | null;
  disposition_accuracy: number | null;
  detection: { precision: number | null; recall: number | null; true_positives: number; false_positives: number } | null;
  cost_usd: { total: string; per_application_mean: string | null; per_application_max: string | null } | null;
}

export interface EvalRunDetail {
  id: string;
  mode: string;
  status: string;
  note: string | null;
  metrics: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  packets: Record<string, any>[]; // eslint-disable-line @typescript-eslint/no-explicit-any
  started_at: string;
  finished_at: string | null;
}

export const DISPOSITION_LABEL: Record<Disposition, string> = {
  INITIAL_REVIEW_PASS: "Initial Review pass",
  DEFICIENCY_NOTICE: "Deficiency notice",
  SUPPLEMENTAL_REVIEW_REQUIRED: "Supplemental Review required",
  NEEDS_ENGINEER_DETERMINATION: "Needs engineer determination",
};
