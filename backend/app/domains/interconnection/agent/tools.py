"""The agent's tools. None of them computes, sends, or approves: screen numbers come only from run_screens."""

import uuid
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.agent import Tool, ToolOutcome
from app.core.models import Document, ExtractedFact
from app.core.rules_search import search_rules
from app.domains.interconnection.agent.evidence import review_json
from app.domains.interconnection.circuits import to_attributes
from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.screen_store import to_rows
from app.domains.interconnection.screens.initial_review import run_initial_review
from app.domains.interconnection.screens.rulebook import RULESET
from app.domains.interconnection.service import ScreeningOutcome, load_circuit

NULLABLE_DECIMAL = {"type": ["string", "null"], "description": "Decimal number as a string, or null for no change"}

TOOLS = [
    Tool("run_screens",
         "Re-run Rule 21 Initial Review (Screens A–M) with hypothetical changes, to explore mitigations such as a "
         "smaller system or a non-export option. Returns every screen result and the disposition floor. The case "
         "itself is not changed. This is the only way to obtain screen numbers.",
         {"type": "object", "additionalProperties": False,
          "required": ["gross_rating_kw", "gross_rating_kva", "exports", "export_option", "short_circuit_pu",
                       "service_transformer_kva", "rationale"],
          "properties": {
              "gross_rating_kw": NULLABLE_DECIMAL, "gross_rating_kva": NULLABLE_DECIMAL,
              "exports": {"type": ["boolean", "null"]},
              "export_option": {"type": ["integer", "null"], "description": "Screen I option number, or null"},
              "short_circuit_pu": NULLABLE_DECIMAL,
              "service_transformer_kva": {**NULLABLE_DECIMAL, "description": "Hypothetical service transformer size (a utility-side upgrade)"},
              "rationale": {"type": "string", "description": "What this scenario tests"},
          }}),
    Tool("get_circuit_model", "The utility circuit data used for this case, including which fields are synthetic.",
         {"type": "object", "additionalProperties": False, "required": [], "properties": {}}),
    Tool("search_rules",
         "Full-text search over the pinned PG&E Electric Rule 21 text. Returns section, heading, sheet and a snippet. "
         "Cite only sections and sheets returned here or in screen results.",
         {"type": "object", "additionalProperties": False, "required": ["query"],
          "properties": {"query": {"type": "string"}}}),
    Tool("get_field_provenance",
         "Every document statement behind a field: an extraction field (e.g. inverter_rated_ac_power) or a "
         "reconciled facility attribute (e.g. gross_rating_kw). Returns document kind, page, quote and value.",
         {"type": "object", "additionalProperties": False, "required": ["field"],
          "properties": {"field": {"type": "string"}}}),
    Tool("flag_deficiency",
         "Record one item the applicant must correct or supply. The basis must point at real evidence: a screen id, "
         "a fact id, a discrepancy field, or a missing document kind. Items without valid evidence are rejected.",
         {"type": "object", "additionalProperties": False,
          "required": ["description", "basis_kind", "basis_ref", "rule_section", "rule_sheet"],
          "properties": {
              "description": {"type": "string", "description": "What is wrong and what the applicant must provide"},
              "basis_kind": {"type": "string", "enum": ["screen", "fact", "discrepancy", "missing_document"]},
              "basis_ref": {"type": "string", "description": "Screen id (e.g. 'I'), fact id, discrepancy field, or document kind"},
              "rule_section": {"type": ["string", "null"]},
              "rule_sheet": {"type": ["integer", "null"]},
          }}),
    Tool("propose_disposition",
         "Finish: write the draft for engineer review. This does not send anything. Code enforces the disposition "
         "floor and checks every number and citation in the letter.",
         {"type": "object", "additionalProperties": False,
          "required": ["disposition", "letter_markdown", "summary_for_engineer"],
          "properties": {
              "disposition": {"type": "string", "enum": [d.value for d in Disposition]},
              "letter_markdown": {"type": "string", "description": "The letter to the applicant, in Markdown"},
              "summary_for_engineer": {"type": "string", "description": "Two or three sentences on what drove the outcome"},
          }},
         terminal=True),
]


@dataclass
class ReviewContext:
    session: Session
    case_id: uuid.UUID
    outcome: ScreeningOutcome
    deficiencies: list[dict[str, Any]] = field(default_factory=list)

    def fact_ids(self) -> set[str]:
        return {str(i) for i in self.session.scalars(select(ExtractedFact.id).where(ExtractedFact.case_id == self.case_id))}

    def basis_is_valid(self, kind: str, ref: str) -> bool:
        rec = self.outcome.reconciliation
        if kind == "screen":
            return ref in {r.screen for r in self.outcome.review.results}
        if kind == "fact":
            return ref in self.fact_ids()
        if kind == "discrepancy":
            return ref in {f.field for f in rec.findings}
        if kind == "missing_document":
            return ref in rec.missing_documents
        return False


def _decimal(name: str, raw: str | None) -> Decimal | None:
    if raw is None:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise ValueError(f"{name} must be a decimal number, got {raw!r}") from exc
    if not value.is_finite() or value < 0:
        raise ValueError(f"{name} must be a non-negative finite number")
    return value


def execute(ctx: ReviewContext, name: str, args: dict[str, Any]) -> ToolOutcome:
    if name == "run_screens":
        overrides: dict[str, Any] = {}
        for key in ("gross_rating_kw", "gross_rating_kva", "short_circuit_pu"):
            if (v := _decimal(key, args.get(key))) is not None:
                overrides[key] = v
        if args.get("exports") is not None:
            overrides["exports"] = args["exports"]
        if args.get("export_option") is not None:
            overrides["export_option"] = args["export_option"]
        inputs = ctx.outcome.inputs
        facility = replace(inputs.facility, **overrides)
        circuit = inputs.circuit
        if (t := _decimal("service_transformer_kva", args.get("service_transformer_kva"))) is not None:
            circuit = replace(circuit, service_transformer_kva=t)
            overrides["service_transformer_kva"] = t
        scenario = replace(inputs, facility=facility, circuit=circuit)
        review = run_initial_review(scenario)
        recorded = {k: str(v) for k, v in overrides.items()} | {"rationale": args.get("rationale", "")}
        ctx.session.add_all(to_rows(ctx.case_id, review, overrides=recorded))
        baseline = {r.screen: r.status for r in ctx.outcome.review.results}
        changed = [f"{r.screen}: {baseline[r.screen].value} → {r.status.value}" for r in review.results
                   if baseline[r.screen] is not r.status]
        return ToolOutcome({"overrides": recorded, "changed_vs_case": changed,
                            **review_json(review, review.disposition_floor())})

    if name == "get_circuit_model":
        circuit, model = load_circuit(ctx.session, ctx.case_id)
        if model is None:
            return ToolOutcome({"resolved": False, "note": "no circuit model is linked to this application; "
                                                           "utility-side screen inputs are unknown"})
        return ToolOutcome({"resolved": True, "utility": model.utility, "feeder_id": model.feeder_id,
                            "line_section_id": model.line_section_id, "source": model.source,
                            "attributes": to_attributes(circuit), "synthetic_fields": sorted(model.synthetic_fields)})

    if name == "search_rules":
        hits = search_rules(ctx.session, RULESET, args["query"], limit=5)
        return ToolOutcome([{"section": h.section, "heading": h.heading, "sheet": h.sheet, "snippet": h.snippet}
                            for h in hits])

    if name == "get_field_provenance":
        field_name = args["field"]
        rec = ctx.outcome.reconciliation
        ids: set[str] | None = None
        derivations: list[str] = []
        if field_name in rec.provenance:
            ids = {i for s in rec.provenance[field_name] for i in s.fact_ids}
            derivations = [s.derivation for s in rec.provenance[field_name] if s.derivation]
        query = select(ExtractedFact, Document.kind).join(Document, ExtractedFact.document_id == Document.id) \
            .where(ExtractedFact.case_id == ctx.case_id)
        rows = [(f, k) for f, k in ctx.session.execute(query).all()
                if (ids is not None and str(f.id) in ids) or (ids is None and f.field == field_name)]
        return ToolOutcome({"field": field_name, "derivations": derivations, "statements": [
            {"fact_id": str(f.id), "field": f.field, "value": f.value, "unit": f.unit, "value_as_written": f.value_as_written,
             "unit_as_written": f.unit_as_written, "document": k, "page": f.page_no, "quote": f.quote,
             "verification": f.verification} for f, k in rows]})

    if name == "flag_deficiency":
        if not ctx.basis_is_valid(args["basis_kind"], args["basis_ref"]):
            return ToolOutcome({"error": f"basis {args['basis_kind']}={args['basis_ref']!r} does not match any evidence "
                                         "in this case; the item was not recorded"}, is_error=True)
        ctx.deficiencies.append({k: args.get(k) for k in ("description", "basis_kind", "basis_ref", "rule_section", "rule_sheet")})
        return ToolOutcome({"recorded": len(ctx.deficiencies)})

    return ToolOutcome({"error": f"unknown tool {name}"}, is_error=True)
