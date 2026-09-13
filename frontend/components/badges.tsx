import type { Disposition, ScreenRow } from "@/lib/api";
import { DISPOSITION_LABEL } from "@/lib/api";

const base = "inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium ring-1 ring-inset whitespace-nowrap";

export function StatusBadge({ status }: { status: ScreenRow["status"] | string }) {
  const tone: Record<string, string> = {
    PASS: "bg-emerald-50 text-emerald-800 ring-emerald-600/20",
    FAIL: "bg-rose-50 text-rose-800 ring-rose-600/20",
    INCONCLUSIVE: "bg-amber-50 text-amber-900 ring-amber-600/25",
    NOT_APPLICABLE: "bg-slate-50 text-slate-600 ring-slate-500/15",
    SKIPPED: "bg-slate-50 text-slate-500 ring-slate-500/10",
  };
  return <span className={`${base} ${tone[status] ?? tone.SKIPPED}`}>{status.replace("_", " ")}</span>;
}

export function DispositionBadge({ disposition }: { disposition: Disposition }) {
  const tone: Record<Disposition, string> = {
    INITIAL_REVIEW_PASS: "bg-emerald-50 text-emerald-800 ring-emerald-600/25",
    DEFICIENCY_NOTICE: "bg-amber-50 text-amber-900 ring-amber-600/30",
    SUPPLEMENTAL_REVIEW_REQUIRED: "bg-rose-50 text-rose-800 ring-rose-600/25",
    NEEDS_ENGINEER_DETERMINATION: "bg-indigo-50 text-indigo-800 ring-indigo-600/25",
  };
  return <span className={`${base} ${tone[disposition]}`}>{DISPOSITION_LABEL[disposition]}</span>;
}

export function ReviewStatusBadge({ status }: { status: string }) {
  const tone: Record<string, string> = {
    pending_review: "bg-sky-50 text-sky-800 ring-sky-600/25",
    approved: "bg-emerald-600 text-white ring-emerald-700",
    edited: "bg-emerald-600 text-white ring-emerald-700",
    rejected: "bg-slate-700 text-white ring-slate-800",
  };
  return <span className={`${base} ${tone[status] ?? "bg-slate-50 text-slate-600 ring-slate-500/15"}`}>{status.replace("_", " ")}</span>;
}

export function Cite({ section, sheet }: { section: string; sheet: number }) {
  return (
    <span className="inline-flex items-center rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-600">
      §{section} · Sheet {sheet}
    </span>
  );
}
