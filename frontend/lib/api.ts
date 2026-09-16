import { CASE_ID, cases, evalDetail, evalRuns, families, review, rules, trace } from "@/mocks/data";
import type {
  ApiErrorDetail,
  CaseDocument,
  DefectFamily,
  DocumentKind,
  EvalDetail,
  EvalRun,
  PageText,
  PortalApplication,
  PortalApplicationSummary,
  Proposal,
  QueueCase,
  ReviewBundle,
  RuleResult,
  TraceRun,
} from "./types";

// In this app the real API is the default; set NEXT_PUBLIC_USE_MOCKS=true to use the local fixtures.
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8010";
const USE_MOCKS = process.env.NEXT_PUBLIC_USE_MOCKS === "true";
const MOCK_CLAUDE_DELAY = Number(process.env.NEXT_PUBLIC_MOCK_CLAUDE_DELAY_MS || 8000);
const wait = (ms = 350) => new Promise((resolve) => setTimeout(resolve, ms));
export class ApiError extends Error {
  constructor(
    public status: number,
    public detail: ApiErrorDetail,
  ) {
    super(
      typeof detail === "string"
        ? detail
        : detail.map((i) => `${i.loc.slice(1).join(".")}: ${i.msg}`).join("; "),
    );
  }
}
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, init);
  if (!response.ok) {
    let body: { detail?: ApiErrorDetail };
    try {
      body = await response.json();
    } catch {
      body = { detail: `Request failed (${response.status})` };
    }
    throw new ApiError(response.status, body.detail ?? `Request failed (${response.status})`);
  }
  return response.json();
}
const mockCases = structuredClone(cases);
const mockReview = structuredClone(review);
function mockProposal(): Proposal {
  if (!mockReview.proposal) throw new ApiError(404, "proposal not found");
  return mockReview.proposal;
}

export async function health() {
  if (USE_MOCKS) {
    await wait();
    return { status: "ok", db: "ok" };
  }
  return request<{ status: string; db: string }>("/health");
}
export async function listCases(): Promise<QueueCase[]> {
  if (USE_MOCKS) {
    await wait();
    return structuredClone(mockCases);
  }
  return request("/cases");
}
export async function getCase(id: string) {
  if (USE_MOCKS) {
    await wait();
    const item = mockCases.find((c) => c.case_id === id);
    if (!item) throw new ApiError(404, "case not found");
    return {
      id: item.case_id,
      domain: item.domain,
      status: item.status,
      submitter: item.submitter,
      received_at: item.received_at,
      documents: mockReview.documents,
    };
  }
  return request(`/cases/${id}`);
}
export async function getReview(id: string): Promise<ReviewBundle> {
  if (USE_MOCKS) {
    await wait();
    if (!mockCases.some((c) => c.case_id === id)) throw new ApiError(404, "case not found");
    return structuredClone(mockReview);
  }
  return request(`/cases/${id}/review`);
}
export async function runReview(
  id: string,
  useLlm = true,
): Promise<{ llm_used: boolean; disposition_floor: string; proposal: Proposal }> {
  if (USE_MOCKS) {
    if (!mockCases.some((c) => c.case_id === id)) throw new ApiError(404, "case not found");
    await wait(useLlm ? MOCK_CLAUDE_DELAY : 500);
    const item = mockCases.find((c) => c.case_id === id);
    if (item) {
      item.status = "pending_review";
      item.proposal = {
        id: mockProposal().id,
        disposition: mockProposal().disposition,
        status: "pending_review",
        guardrail_failures: 1,
      };
    }
    return {
      llm_used: useLlm,
      disposition_floor: "DEFICIENCY_NOTICE",
      proposal: structuredClone(mockProposal()),
    };
  }
  return request(`/cases/${id}/review?use_llm=${useLlm}`, { method: "POST" });
}
export async function getTrace(id: string): Promise<TraceRun[]> {
  if (USE_MOCKS) {
    await wait();
    return structuredClone(trace);
  }
  return request(`/cases/${id}/trace`);
}
export async function decide(
  id: string,
  input: {
    action: "approve" | "edit" | "reject";
    reviewer: string;
    note?: string;
    letter_md?: string | null;
  },
): Promise<Proposal> {
  if (USE_MOCKS) {
    await wait();
    if (!input.reviewer.trim())
      throw new ApiError(422, [
        {
          type: "string_too_short",
          loc: ["body", "reviewer"],
          msg: "String should have at least 1 character",
          input: "",
        },
      ]);
    if (input.action === "edit" && !input.letter_md)
      throw new ApiError(422, "edit requires the revised letter_md");
    if (mockProposal().status !== "pending_review")
      throw new ApiError(409, `proposal was already ${mockProposal().status}`);
    mockReview.proposal = {
      ...mockProposal(),
      status:
        input.action === "approve" ? "approved" : input.action === "edit" ? "edited" : "rejected",
      letter_md:
        input.action === "edit"
          ? (input.letter_md ?? mockProposal().letter_md)
          : mockProposal().letter_md,
      reviewed_by: input.reviewer,
      reviewed_at: new Date().toISOString(),
      review_note: input.note ?? null,
    };
    return structuredClone(mockProposal());
  }
  return request(`/proposals/${id}/decision`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
export async function listEvals(): Promise<EvalRun[]> {
  if (USE_MOCKS) {
    await wait();
    return structuredClone(evalRuns);
  }
  return request("/evals");
}
export async function getEval(id: string): Promise<EvalDetail> {
  if (USE_MOCKS) {
    await wait();
    const first = evalRuns.at(0);
    if (!evalRuns.some((r) => r.id === id)) throw new ApiError(404, "eval run not found");
    return structuredClone({ ...evalDetail, id, mode: id === first?.id ? "oracle" : "live" });
  }
  return request(`/evals/${id}`);
}
export async function listFamilies(): Promise<DefectFamily[]> {
  if (USE_MOCKS) {
    await wait();
    return structuredClone(families);
  }
  return request("/evals/families");
}
export async function createDemoPacket(input: {
  family: string;
  seed?: number;
  oracle_facts?: boolean;
}) {
  if (USE_MOCKS) {
    await wait();
    const family = families.find((f) => f.name === input.family);
    if (!family)
      throw new ApiError(
        422,
        `family must be one of [${families.map((f) => `'${f.name}'`).join(", ")}]`,
      );
    return {
      case_id: CASE_ID,
      family: family.name,
      expected_disposition: family.expected,
      description: family.description,
      oracle_facts: input.oracle_facts ?? false,
    };
  }
  return request("/demo/packets", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
export async function createApplication(input: {
  utility: string;
  submitter?: string;
  applicant_name?: string;
  site_address?: string;
}) {
  if (USE_MOCKS) {
    await wait();
    if (!input.utility)
      throw new ApiError(422, [
        { type: "missing", loc: ["body", "utility"], msg: "Field required", input },
      ]);
    return { case_id: "8d8a6fd0-542e-40eb-9354-56b623e4b22c", status: "received" as const };
  }
  return request<{ case_id: string; status: "received" }>("/interconnection/applications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
export async function uploadDocument(
  caseId: string,
  kind: DocumentKind,
  file: File,
): Promise<CaseDocument> {
  if (USE_MOCKS) {
    await wait(700);
    if (file.size > 26214400) throw new ApiError(413, "file exceeds 26214400 bytes");
    if (file.type !== "application/pdf" && !file.name.toLowerCase().endsWith(".pdf"))
      throw new ApiError(422, "file is not a PDF");
    return {
      id: crypto.randomUUID(),
      kind,
      filename: file.name,
      sha256: "c697a2bdc5296d192f15ee18d7c9cb7b14195c8ae86532b5f7442cce826b97c1",
      page_count: 2,
      created_at: new Date().toISOString(),
      pages: [
        { page_no: 1, anchor: "c697a2bdc529#p1", has_text_layer: true, char_count: 232 },
        { page_no: 2, anchor: "c697a2bdc529#p2", has_text_layer: true, char_count: 274 },
      ],
    };
  }
  const body = new FormData();
  body.append("kind", kind);
  body.append("file", file);
  return request(`/cases/${caseId}/documents`, { method: "POST", body });
}
export function documentFileUrl(caseId: string, documentId: string, page?: number) {
  return `${API_URL}/cases/${caseId}/documents/${documentId}/file${page ? `#page=${page}` : ""}`;
}
export async function getDocumentPage(
  caseId: string,
  documentId: string,
  pageNo: number,
): Promise<PageText> {
  if (USE_MOCKS) {
    await wait();
    const fact = mockReview.facts.find((f) => f.document_id === documentId && f.page_no === pageNo);
    return {
      document_id: documentId,
      page_no: pageNo,
      anchor: `mock#p${pageNo}`,
      has_text_layer: true,
      text: `PG&E Rule 21 Interconnection Request\n${fact?.quote ?? "Document evidence page"}\nService address: ${mockReview.application?.site_address ?? ""}\nInstaller: Golden State Solar\nTariff: Net Billing Tariff (NBT-1)`,
    };
  }
  return request(`/cases/${caseId}/documents/${documentId}/pages/${pageNo}`);
}
export async function extractDocument(caseId: string, documentId: string) {
  if (USE_MOCKS) {
    await wait(MOCK_CLAUDE_DELAY);
    return {
      document_id: documentId,
      model: "claude-opus-5",
      cost_usd: "0.0231",
      accepted: [],
      rejected: [],
    };
  }
  return request(`/cases/${caseId}/documents/${documentId}/extract`, { method: "POST" });
}
export async function searchRules(q: string, limit = 5): Promise<RuleResult[]> {
  if (USE_MOCKS) {
    await wait();
    if (q.length < 2)
      throw new ApiError(422, [
        {
          type: "string_too_short",
          loc: ["query", "q"],
          msg: "String should have at least 2 characters",
          input: q,
        },
      ]);
    return structuredClone(rules.slice(0, limit));
  }
  return request(`/rules/search?q=${encodeURIComponent(q)}&limit=${limit}`);
}

/* ---- Applicant portal (live API only; the mock fixtures predate the portal) ---- */
function livePortal() {
  if (USE_MOCKS) throw new ApiError(501, "The applicant portal needs the live API; unset NEXT_PUBLIC_USE_MOCKS.");
}
export async function listPortalApplications(installer: string): Promise<PortalApplicationSummary[]> {
  livePortal();
  return request(`/portal/applications?installer=${encodeURIComponent(installer)}`);
}
export async function startPortalApplication(input: {
  installer: string;
  applicant_name: string;
  site_address: string;
  contact_email?: string;
}): Promise<PortalApplication> {
  livePortal();
  return request("/portal/applications", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}
export async function getPortalApplication(id: string): Promise<PortalApplication> {
  livePortal();
  return request(`/portal/applications/${id}`);
}
export async function uploadPortalDocument(id: string, kind: DocumentKind, file: File): Promise<PortalApplication> {
  livePortal();
  const body = new FormData();
  body.append("kind", kind);
  body.append("file", file);
  return request(`/portal/applications/${id}/documents`, { method: "POST", body });
}
export async function submitPortalApplication(id: string): Promise<PortalApplication> {
  livePortal();
  return request(`/portal/applications/${id}/submit`, { method: "POST" });
}
