export type Disposition =
  | "INITIAL_REVIEW_PASS"
  | "DEFICIENCY_NOTICE"
  | "SUPPLEMENTAL_REVIEW_REQUIRED"
  | "NEEDS_ENGINEER_DETERMINATION";
export type ProposalStatus = "pending_review" | "approved" | "edited" | "rejected";
export type CaseStatus =
  | "received"
  | "extracting"
  | "reconciling"
  | "screening"
  | "agent_review"
  | "pending_review"
  | "closed";
export type ScreenStatus = "PASS" | "FAIL" | "INCONCLUSIVE" | "NOT_APPLICABLE" | "SKIPPED";
export type DocumentKind =
  | "application_form"
  | "one_line_diagram"
  | "site_plan"
  | "inverter_spec_sheet"
  | "battery_spec_sheet"
  | "customer_authorization"
  | "other";

export interface QueueCase {
  case_id: string;
  domain: string;
  status: CaseStatus;
  submitter: string | null;
  received_at: string;
  applicant_name: string | null;
  site_address: string | null;
  documents: number;
  /** How many times the applicant has sent it: 1 for a first submission, more after corrections. 0 = not via the portal. */
  submissions?: number;
  proposal: null | {
    id: string;
    disposition: Disposition;
    status: ProposalStatus;
    guardrail_failures: number;
  };
}
export interface DocumentPage {
  page_no: number;
  anchor: string;
  has_text_layer: boolean;
  char_count?: number;
}
export interface CaseDocument {
  id: string;
  kind: DocumentKind;
  filename: string;
  sha256: string;
  page_count: number;
  created_at?: string;
  pages: DocumentPage[];
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
  document_kind: DocumentKind;
  page_no: number;
  quote: string;
  verification: string;
}
export interface DiscrepancySource {
  fact_ids: string[];
  derivation: string | null;
}
export interface Discrepancy {
  field: string;
  observed: Array<{ value: string | number | boolean | null; chosen: boolean; sources: DiscrepancySource[] }>;
  material: boolean | null;
  method: "llm" | "rule_outcome" | null;
  rationale: string | null;
}
export interface Citation {
  quote?: string;
  sheet: number;
  section: string;
  interpretation?: string;
}
export interface Screen {
  screen: string;
  status: ScreenStatus;
  reason: string | null;
  formula: string | null;
  computed: string | null;
  threshold: string | null;
  inputs: Record<string, string>;
  citations: Citation[];
  classification: string | null;
  blocker: "applicant" | "utility" | null;
  routed_by: string | null;
  missing_inputs: string[];
  synthetic_inputs: string[];
  overrides: Record<string, unknown>;
  input_hash: string;
  engine_version: string;
}
export interface GuardrailVerdict {
  data: Record<string, unknown>;
  name: string;
  detail: string;
  passed: boolean;
}
export interface ProposalItem {
  basis_ref: string;
  basis_kind: "screen" | "fact" | "discrepancy" | "missing_document";
  rule_sheet: number | null;
  description: string;
  rule_section: string | null;
}
export interface Proposal {
  id: string;
  disposition: Disposition;
  model_disposition: Disposition | null;
  status: ProposalStatus;
  letter_md: string;
  items: ProposalItem[];
  guardrail_verdicts: GuardrailVerdict[];
  agent_run_id: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
}
export interface ReviewBundle {
  case: { id: string; status: CaseStatus; submitter: string | null; received_at: string };
  application: {
    utility: string;
    applicant_name: string | null;
    site_address: string | null;
    circuit_model_id: string | null;
  } | null;
  documents: CaseDocument[];
  replaced_documents?: ReplacedDocument[];
  facts: Fact[];
  discrepancies: Discrepancy[];
  screens: Screen[];
  scenarios: Screen[];
  proposal: Proposal | null;
  notifications?: AppNotification[];
  _note?: string;
}
export interface TraceStep {
  n: number;
  role: string;
  tool: string | null;
  args: Record<string, unknown> | null;
  result: Record<string, unknown>;
  input_tokens: number | null;
  output_tokens: number | null;
  cost_usd: string | null;
  latency_ms: number | null;
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
  steps: TraceStep[];
  _note?: string;
}
export interface DetectionMetrics {
  recall: number | null;
  precision: number | null;
  true_positives: number;
  false_positives: number;
}
export interface EvalRun {
  id: string;
  mode: "oracle" | "live";
  status: "running" | "completed" | "stopped" | "failed";
  note: string | null;
  started_at: string;
  finished_at: string | null;
  packets: number | null;
  disposition_accuracy: number | null;
  detection: DetectionMetrics | null;
  cost_usd: null | { total: string; per_application_max: string | null; per_application_mean: string | null };
}
export interface EvalPacket {
  family: string;
  case_id: string;
  correct: boolean;
  profile: string;
  cost_usd: string;
  detected: Array<{ ref: string; kind: string }>;
  spurious: unknown[];
  agent_run: string | null;
  latency_s: number;
  llm_calls: number;
  packet_id: string;
  extraction: null | Record<string, unknown>;
  guardrails: Record<string, boolean>;
  disposition: Disposition;
  proposal_id: string;
  consequential: unknown[];
  deterministic: boolean;
  disposition_floor: Disposition;
  model_disposition: Disposition | null;
  expected_detections: Array<{ ref: string; kind: string }>;
  expected_disposition: Disposition;
}
export interface EvalDetail {
  id: string;
  mode: "oracle" | "live";
  status: EvalRun["status"];
  note: string | null;
  config: Record<string, string>;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any -- metrics vary by eval mode; rendered defensively
  metrics: Record<string, any>;
  packets: EvalPacket[];
  started_at: string;
  finished_at: string | null;
}
export interface DefectFamily {
  name: string;
  profile: string;
  expected: Disposition;
  description: string;
}
export interface RuleResult {
  ruleset: string;
  section: string;
  heading: string;
  sheet: number;
  snippet: string;
  rank: number;
}
export interface PageText {
  document_id: string;
  page_no: number;
  anchor: string;
  has_text_layer: boolean;
  text: string;
}
export interface ApiValidationIssue {
  type: string;
  loc: Array<string | number>;
  msg: string;
  input?: unknown;
  ctx?: Record<string, unknown>;
}
export type ApiErrorDetail = string | ApiValidationIssue[];

export interface ReplacedDocument {
  id: string;
  kind: DocumentKind;
  filename: string;
  page_count: number;
  uploaded_at: string;
  replaced_at: string;
}

/* ---- Applicant portal: only what an applicant may see ---- */
export type PortalStatus =
  | "draft"
  | "under_review"
  | "action_required"
  | "passed_initial_review"
  | "supplemental_review"
  | "engineering_review";
export interface PortalDocument {
  id: string;
  kind: DocumentKind;
  label: string;
  filename: string;
  page_count: number;
  uploaded_at: string;
  replaced_at: string | null;
}
export interface PortalLetter {
  id: string;
  outcome: PortalStatus;
  outcome_label: string;
  letter_md: string;
  issued_at: string;
  issued_by: string;
}
export interface PortalTimelineEntry {
  at: string;
  kind: string;
  label: string;
  detail: string | null;
}
export interface AppNotification {
  kind: string;
  subject: string;
  recipient: string | null;
  status: "queued" | "sent" | "failed" | "no_recipient";
  created_at: string;
  sent_at: string | null;
  error?: string | null;
}
export interface PortalApplication {
  id: string;
  reference: string;
  installer: string;
  utility: string;
  applicant_name: string;
  site_address: string;
  contact_email: string | null;
  status: PortalStatus;
  status_label: string;
  status_detail: string;
  started_at: string;
  submitted_at: string | null;
  required_documents: { kind: DocumentKind; label: string; uploaded: boolean }[];
  documents: PortalDocument[];
  replaced_documents: PortalDocument[];
  can_upload: boolean;
  can_submit: boolean;
  submit_blocker: string | null;
  letters: PortalLetter[];
  timeline: PortalTimelineEntry[];
  notifications: AppNotification[];
}
export interface PortalApplicationSummary {
  id: string;
  reference: string;
  applicant_name: string;
  site_address: string;
  status: PortalStatus;
  status_label: string;
  updated_at: string;
  documents: number;
}
