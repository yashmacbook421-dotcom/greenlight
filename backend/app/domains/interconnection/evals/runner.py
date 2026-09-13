"""Run the review pipeline over a generated corpus and score it against ground truth.

Modes:
- oracle — the generator's exact facts are inserted (after passing the same verifier extraction uses) and an
  oracle judge answers identity-conflict materiality. No model calls. Measures everything downstream of
  extraction: reconciliation, screens, disposition, guardrails, determinism.
- live — Claude extracts, judges and drafts. Adds extraction precision/recall, cost and latency. Costs money;
  a hard ceiling stops the run.
"""

import time
import uuid
from collections import Counter, defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.extraction import AcceptedFact, Candidate, verify
from app.core.llm import MessagesClient, MeteredClient
from app.core.models import Case, Document, EvalRun, ExtractedFact
from app.core.storage import LocalStorage
from app.domains.interconnection import DOMAIN
from app.domains.interconnection.circuits import to_attributes
from app.domains.interconnection.evals.generator import Packet
from app.domains.interconnection.extraction_fields import FIELDS
from app.domains.interconnection.models import CircuitModel, InterconnectionApplication
from app.domains.interconnection.pipeline import review_case
from app.domains.interconnection.reconcile import Judgment
from app.domains.interconnection.screens.initial_review import run_initial_review
from app.domains.interconnection.screens.types import Blocker, Classification, Status
from app.core.intake import ingest_document

SPECS = {s.name: s for s in FIELDS}


class GeneratorError(RuntimeError):
    """A generated oracle fact failed verification against its own PDF: a bug in the generator, not the system."""


def load_packet(session: Session, storage: LocalStorage, packet: Packet, tag: str) -> tuple[Case, dict[str, Document]]:
    case = Case(domain=DOMAIN, submitter=f"[eval {tag}] {packet.installer_name}")
    session.add(case)
    session.flush()
    circuit = CircuitModel(utility="PGE", feeder_id=f"EVAL-{tag}-{packet.packet_id}", line_section_id="LS-1",
                           source="synthetic (Greenlight eval generator)", attributes=to_attributes(packet.circuit),
                           synthetic_fields=packet.synthetic_fields)
    session.add(circuit)
    session.flush()
    session.add(InterconnectionApplication(case_id=case.id, utility="PGE", applicant_name=packet.applicant_name,
                                           site_address=packet.site_address, circuit_model_id=circuit.id))
    docs = {}
    for d in packet.documents:
        docs[d.kind], _ = ingest_document(session, storage, case_id=case.id, kind=d.kind, filename=d.filename,
                                          data=d.data, max_pages=50)
    session.flush()
    return case, docs


def insert_oracle_facts(session: Session, case: Case, docs: dict[str, Document], packet: Packet) -> None:
    for f in packet.facts:
        doc = docs[f.document_kind]
        pages = {p.page_no: (p.text, p.has_text_layer) for p in doc.pages}
        outcome = verify(Candidate(f.field, f.value_as_written, f.unit_as_written, f.page, f.quote, f.instance), SPECS, pages)
        if not isinstance(outcome, AcceptedFact):
            raise GeneratorError(f"{packet.packet_id}: oracle fact {f.field} rejected ({outcome.reason}) — generator bug")
        session.add(ExtractedFact(case_id=case.id, document_id=doc.id, page_no=f.page, field=f.field, value=outcome.value,
                                  unit=outcome.unit, value_as_written=f.value_as_written, unit_as_written=f.unit_as_written,
                                  quote=f.quote, instance=f.instance, verification="oracle", extracted_by="oracle"))
    session.flush()


def oracle_judge(packet: Packet) -> Callable[..., list[Judgment]]:
    def judge(findings, facts):
        return [Judgment(f.field in packet.identity_conflicts,
                         "oracle: injected conflict" if f.field in packet.identity_conflicts else "oracle: not injected")
                for f in findings]
    return judge


def _signals(outcome: Any) -> list[dict[str, str]]:
    """What the review surfaced as problems, in the same vocabulary as the ground truth."""
    rec, review = outcome.screening.reconciliation, outcome.screening.review
    signals = [{"kind": "missing_document", "ref": d} for d in rec.missing_documents]
    signals += [{"kind": "discrepancy", "ref": f.field} for f in rec.findings if f.material]
    for r in review.results:
        if r.status is Status.FAIL and r.classification is not Classification.ROUTING:
            signals.append({"kind": "screen", "ref": r.screen, "status": "FAIL"})
        elif r.status is Status.INCONCLUSIVE and r.blocker is Blocker.APPLICANT and not r.routed_by:
            signals.append({"kind": "screen", "ref": r.screen, "status": "INCONCLUSIVE"})
    return signals


def _matches(expected: dict[str, str], signal: dict[str, str]) -> bool:
    return all(signal.get(k) == v for k, v in expected.items())


def extraction_score(session: Session, case: Case, packet: Packet) -> dict[str, Any]:
    rows = session.execute(select(ExtractedFact, Document.kind).join(Document, ExtractedFact.document_id == Document.id)
                           .where(ExtractedFact.case_id == case.id)).all()
    got = Counter((kind, f.field, str(f.value)) for f, kind in rows)
    want: Counter[tuple[str, str, str]] = Counter()
    for f in packet.facts:
        spec = SPECS[f.field]
        pages = {f.page: (f.quote, True)}
        accepted = verify(Candidate(f.field, f.value_as_written, f.unit_as_written, f.page, f.quote), {f.field: spec}, pages)
        want[(f.document_kind, f.field, accepted.value if isinstance(accepted, AcceptedFact) else f.value_as_written)] += 1
    true_positive = sum((got & want).values())
    return {"expected": sum(want.values()), "extracted": sum(got.values()), "matched": true_positive,
            "recall": round(true_positive / sum(want.values()), 4) if want else None,
            "precision": round(true_positive / sum(got.values()), 4) if got else None,
            "missed": sorted({f"{k[0]}:{k[1]}" for k in (want - got)}),
            "unexpected": sorted({f"{k[0]}:{k[1]}={k[2]}" for k in (got - want)})}


@dataclass
class RunConfig:
    mode: str
    max_cost_usd: Decimal = Decimal("5.00")


def evaluate_packet(session: Session, storage: LocalStorage, packet: Packet, cfg: RunConfig, client: MessagesClient | None,
                    tag: str) -> dict[str, Any]:
    started = time.monotonic()
    case, docs = load_packet(session, storage, packet, tag)
    metered = MeteredClient(client) if client is not None else None
    extraction: dict[str, Any] | None = None
    if cfg.mode == "oracle":
        insert_oracle_facts(session, case, docs, packet)
        outcome = review_case(session, case, client=None, storage=storage, judge=oracle_judge(packet))
    else:
        outcome = review_case(session, case, client=metered, storage=storage)
        extraction = extraction_score(session, case, packet)
        extraction["rejected"] = dict(Counter(r.reason.value for e in outcome.extractions for r in e.rejected))
    latency_s = round(time.monotonic() - started, 2)

    expected = list(packet.family.detections)
    signals = _signals(outcome)
    allowed = expected + list(packet.family.consequences)
    detected = [e for e in expected if any(_matches(e, s) for s in signals)]
    consequential = [s for s in signals if not any(_matches(e, s) for e in expected)
                     and any(_matches(c, s) for c in packet.family.consequences)]
    spurious = [s for s in signals if not any(_matches(a, s) for a in allowed)]

    repeats = [run_initial_review(outcome.screening.inputs) for _ in range(3)]
    deterministic = all(r == repeats[0] for r in repeats) and repeats[0].input_hash == outcome.screening.review.input_hash

    verdicts = {v["name"]: v["passed"] for v in outcome.proposal.guardrail_verdicts if v["name"] != "summary_for_engineer"}
    session.commit()
    return {
        "packet_id": packet.packet_id, "family": packet.family.name, "profile": packet.family.profile,
        "case_id": str(case.id), "proposal_id": str(outcome.proposal.id),
        "expected_disposition": packet.family.expected.value, "disposition": outcome.proposal.disposition,
        "disposition_floor": outcome.screening.floor.value, "model_disposition": outcome.proposal.model_disposition,
        "correct": outcome.proposal.disposition == packet.family.expected.value,
        "expected_detections": expected, "detected": detected, "consequential": consequential, "spurious": spurious,
        "guardrails": verdicts, "deterministic": deterministic,
        "agent_run": str(outcome.proposal.agent_run_id) if outcome.proposal.agent_run_id else None,
        "extraction": extraction, "latency_s": latency_s,
        "cost_usd": format(metered.cost_usd, "f") if metered else "0",
        "llm_calls": len(metered.calls) if metered else 0,
    }


def aggregate(results: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    ok = [r for r in results if "error" not in r]
    n = len(ok)
    confusion: dict[str, Counter[str]] = defaultdict(Counter)
    for r in ok:
        confusion[r["expected_disposition"]][r["disposition"]] += 1
    families: dict[str, dict[str, Any]] = {}
    for fam in sorted({r["family"] for r in ok}):
        rs = [r for r in ok if r["family"] == fam]
        exp = sum(len(r["expected_detections"]) for r in rs)
        families[fam] = {
            "packets": len(rs), "disposition_accuracy": round(sum(r["correct"] for r in rs) / len(rs), 4),
            "detection_recall": round(sum(len(r["detected"]) for r in rs) / exp, 4) if exp else None,
            "spurious_signals": sum(len(r["spurious"]) for r in rs),
            "consequential_signals": sum(len(r.get("consequential", [])) for r in rs),
        }
    tp = sum(len(r["detected"]) for r in ok)
    fp = sum(len(r["spurious"]) for r in ok)
    expected_total = sum(len(r["expected_detections"]) for r in ok)

    def rate(name: str) -> float | None:
        vals = [r["guardrails"].get(name) for r in ok if name in r["guardrails"]]
        return round(sum(1 for v in vals if not v) / len(vals), 4) if vals else None

    costs = [Decimal(r["cost_usd"]) for r in ok]
    metrics: dict[str, Any] = {
        "packets": len(results), "errors": len(results) - n,
        "disposition_accuracy": round(sum(r["correct"] for r in ok) / n, 4) if n else None,
        "confusion": {k: dict(v) for k, v in confusion.items()},
        "detection": {"precision": round(tp / (tp + fp), 4) if tp + fp else None,
                      "recall": round(tp / expected_total, 4) if expected_total else None,
                      "true_positives": tp, "false_positives": fp},
        "families": families,
        "guardrail_failure_rates": {name: rate(name) for name in
                                    ("disposition_veto", "number_faithfulness", "citation_validity", "provenance_completeness")},
        "determinism_pass_rate": round(sum(r["deterministic"] for r in ok) / n, 4) if n else None,
        "latency_s": {"mean": round(sum(r["latency_s"] for r in ok) / n, 2) if n else None,
                      "max": max((r["latency_s"] for r in ok), default=None)},
    }
    if mode == "live":
        ex = [r["extraction"] for r in ok if r["extraction"]]
        metrics["extraction"] = {
            "recall_mean": round(sum(e["recall"] or 0 for e in ex) / len(ex), 4) if ex else None,
            "precision_mean": round(sum(e["precision"] or 0 for e in ex) / len(ex), 4) if ex else None,
            "rejections": dict(sum((Counter(e["rejected"]) for e in ex), Counter())),
        }
        metrics["cost_usd"] = {"total": format(sum(costs, Decimal(0)), "f"),
                               "per_application_mean": format(sum(costs, Decimal(0)) / n, ".4f") if n else None,
                               "per_application_max": format(max(costs), "f") if costs else None}
        metrics["llm_calls_mean"] = round(sum(r["llm_calls"] for r in ok) / n, 2) if n else None
    return metrics


def run_eval(session_factory: Callable[[], Session], storage: LocalStorage, packets: list[Packet], cfg: RunConfig,
             client: MessagesClient | None = None, note: str | None = None,
             on_packet: Callable[[dict[str, Any]], None] | None = None) -> uuid.UUID:
    if cfg.mode == "live" and client is None:
        raise ValueError("live mode needs a Claude client")
    with session_factory() as s:
        run = EvalRun(domain=DOMAIN, mode=cfg.mode, note=note,
                      config={"packets": [p.packet_id for p in packets], "max_cost_usd": str(cfg.max_cost_usd)})
        s.add(run)
        s.commit()
        run_id = run.id
    tag = str(run_id)[:8]
    results: list[dict[str, Any]] = []
    spent = Decimal(0)
    status = "completed"
    for packet in packets:
        if cfg.mode == "live" and spent >= cfg.max_cost_usd:
            status = "stopped"
            break
        with session_factory() as s:
            try:
                result = evaluate_packet(s, storage, packet, cfg, client, tag)
            except Exception as exc:  # one bad packet must not lose the run
                s.rollback()
                result = {"packet_id": packet.packet_id, "family": packet.family.name, "error": f"{type(exc).__name__}: {exc}"}
        spent += Decimal(result.get("cost_usd", "0"))
        results.append(result)
        if on_packet:
            on_packet(result)
    with session_factory() as s:
        run = s.get(EvalRun, run_id)
        assert run is not None
        run.packets = results
        run.metrics = aggregate(results, cfg.mode)
        run.status = status
        run.finished_at = datetime.now(UTC)
        s.commit()
    return run_id
