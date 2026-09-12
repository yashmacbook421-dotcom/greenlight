from pathlib import Path
from types import SimpleNamespace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.intake import ingest_document
from app.core.models import Case, Discrepancy, Document, ExtractedFact, RuleResult
from app.core.storage import LocalStorage
from app.domains.interconnection import DOMAIN
from app.domains.interconnection.circuits import to_attributes, to_circuit
from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.models import CircuitModel, InterconnectionApplication
from app.domains.interconnection.service import screen_case
from tests.fakes import FakeClient, usage
from tests.pdfs import text_pdf
from tests.test_initial_review import COMMERCIAL


def test_circuit_attributes_round_trip() -> None:
    model = CircuitModel(utility="PGE", feeder_id="F", line_section_id="S", source="t",
                         attributes=to_attributes(COMMERCIAL.circuit), synthetic_fields=["service_transformer_kva"])
    circuit = to_circuit(model)
    assert circuit.protective_devices == COMMERCIAL.circuit.protective_devices
    assert circuit.ica_sg_min_kw == COMMERCIAL.circuit.ica_sg_min_kw
    assert circuit.synthetic_fields == frozenset({"service_transformer_kva"})


def _packet(session: Session, tmp_path: Path) -> Case:
    storage = LocalStorage(tmp_path)
    case = Case(domain=DOMAIN)
    session.add(case)
    session.flush()
    circuit = CircuitModel(utility="PGE", feeder_id="F1", line_section_id="S1", source="synthetic",
                           attributes={"networked_secondary": False, "service_transformer_kva": "50",
                                       "existing_gross_on_service_transformer_kva": "5"},
                           synthetic_fields=["service_transformer_kva", "existing_gross_on_service_transformer_kva"])
    session.add(circuit)
    session.flush()
    session.add(InterconnectionApplication(case_id=case.id, utility="PGE", circuit_model_id=circuit.id))
    docs = {}
    for kind, body in [("application_form", "System AC rating 7.6 kW\nApplicant Jordan Rivera"),
                       ("one_line_diagram", "Applicant Sam Chen"), ("inverter_spec_sheet", "SE7600H-US")]:
        docs[kind], _ = ingest_document(session, storage, case_id=case.id, kind=kind, filename=f"{kind}.pdf",
                                        data=text_pdf(body), max_pages=5)
    for kind, field, value, unit, quote in [
        ("application_form", "system_ac_rating", "7.6", "kW", "System AC rating 7.6 kW"),
        ("application_form", "system_apparent_power_rating", "7.6", "kVA", "7.6 kVA"),
        ("application_form", "export_intent", "export", None, "export"),
        ("application_form", "tariff_program", "NBT-1", None, "NBT"),
        ("application_form", "applicant_name", "Jordan Rivera", None, "Applicant Jordan Rivera"),
        ("one_line_diagram", "applicant_name", "Sam Chen", None, "Applicant Sam Chen"),
        ("inverter_spec_sheet", "inverter_model", "SE7600H-US", None, "SE7600H-US"),
        ("inverter_spec_sheet", "inverter_phase_configuration", "single_phase_240v_split", None, "240"),
        ("inverter_spec_sheet", "inverter_max_continuous_output_current", "32", "A", "32 A"),
        ("inverter_spec_sheet", "inverter_max_fault_current", "35.2", "A", "35.2 A"),
    ]:
        session.add(ExtractedFact(case_id=case.id, document_id=docs[kind].id, page_no=1, field=field, value=value,
                                  unit=unit, quote=quote, verification="oracle"))
    session.flush()
    return case


def test_screen_case_persists_results_and_discrepancies(session: Session, tmp_path: Path) -> None:
    case = _packet(session, tmp_path)
    outcome = screen_case(session, case)  # no LLM: the name conflict stays unjudged
    assert outcome.floor is Disposition.NEEDS_ENGINEER_DETERMINATION
    rows = session.scalars(select(RuleResult).where(RuleResult.case_id == case.id)).all()
    assert len(rows) == 14
    assert "circuit.service_transformer_kva" in next(r for r in rows if r.rule_id == "D").synthetic_inputs
    [d] = session.scalars(select(Discrepancy).where(Discrepancy.case_id == case.id)).all()
    assert d.field == "applicant_name" and d.material is None and d.method is None

    screen_case(session, case)  # re-running replaces rather than duplicates
    assert len(session.scalars(select(RuleResult).where(RuleResult.case_id == case.id)).all()) == 14


def test_screen_case_with_llm_judge(session: Session, tmp_path: Path) -> None:
    case = _packet(session, tmp_path)

    def respond(kwargs):
        parsed = kwargs["output_format"].model_validate(
            {"judgments": [{"conflict_index": 0, "material": True, "rationale": "Different applicants named."}]})
        return SimpleNamespace(parsed_output=parsed, stop_reason="end_turn", usage=usage(), model="claude-opus-5",
                               _request_id="r", stop_details=None)

    client = FakeClient(respond)
    outcome = screen_case(session, case, client)
    assert outcome.floor is Disposition.DEFICIENCY_NOTICE
    prompt = client.messages.requests[0]["messages"][0]["content"][0]["text"]
    assert "Sam Chen" in prompt and "Jordan Rivera" in prompt and 'page="1"' in prompt
    [d] = session.scalars(select(Discrepancy).where(Discrepancy.case_id == case.id)).all()
    assert (d.material, d.method, d.rationale) == (True, "llm", "Different applicants named.")
