"use client";

import { Badge } from "./ui";
import { Bot, CheckCircle2, Database, ShieldCheck, TriangleAlert } from "lucide-react";
import type { Disposition, ScreenStatus } from "@/lib/types";
export const dispositionLabel: Record<Disposition, string> = {
  INITIAL_REVIEW_PASS: "Initial Review pass",
  DEFICIENCY_NOTICE: "Deficiency notice",
  SUPPLEMENTAL_REVIEW_REQUIRED: "Supplemental Review required",
  NEEDS_ENGINEER_DETERMINATION: "Needs engineer determination",
};
export function DispositionBadge({ value }: { value: Disposition }) {
  const tone =
    value === "INITIAL_REVIEW_PASS" ? "green" : value === "DEFICIENCY_NOTICE" ? "amber" : "red";
  return <Badge tone={tone}>{dispositionLabel[value]}</Badge>;
}
export function ScreenBadge({ status }: { status: ScreenStatus }) {
  const tone =
    status === "PASS"
      ? "green"
      : status === "FAIL"
        ? "red"
        : status === "INCONCLUSIVE"
          ? "amber"
          : "neutral";
  return <Badge tone={tone}>{status.replaceAll("_", " ")}</Badge>;
}
export function TrustTag({ kind }: { kind: "code" | "ai" | "synthetic" | "override" }) {
  const map = {
    code: [ShieldCheck, "Verified by code", "green"],
    ai: [Bot, "Judged by AI", "blue"],
    synthetic: [Database, "Synthetic data", "amber"],
    override: [TriangleAlert, "Code overrode the AI", "red"],
  } as const;
  const [Icon, label, tone] = map[kind];
  return (
    <Badge tone={tone}>
      <Icon size={12} />
      {label}
    </Badge>
  );
}
export function VerdictIcon({ passed }: { passed: boolean }) {
  return passed ? (
    <CheckCircle2 className="text-success" size={18} />
  ) : (
    <TriangleAlert className="text-danger" size={18} />
  );
}
