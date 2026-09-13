from decimal import Decimal as D
from itertools import count

import pytest

from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.reconcile import FactView, Judgment, Method, disposition_floor, reconcile
from app.domains.interconnection.screens.initial_review import run_initial_review
from app.domains.interconnection.screens.types import Circuit, Program, ScreenInputs, UtilityPractice

PRACTICE = UtilityPractice("synthetic, tests", D("1.0"), D("5"))
CIRCUIT = Circuit(networked_secondary=False, service_transformer_kva=D("50"), existing_gross_on_service_transformer_kva=D("5"))
DOCS = ["application_form", "one_line_diagram", "inverter_spec_sheet"]
_ids = count()


def fv(field: str, value: str, unit: str | None = None, kind: str = "application_form", instance: str | None = None,
       page: int = 1) -> FactView:
    return FactView(f"f{next(_ids)}", field, value, unit, instance, kind, page, f"{field}: {value}")


def residential(**override: str) -> list[FactView]:
    base = {
        "system_ac_rating": fv("system_ac_rating", "7.6", "kW"),
        "system_apparent_power_rating": fv("system_apparent_power_rating", "7.6", "kVA"),
        "inverter_model": fv("inverter_model", "SE7600H-US", kind="inverter_spec_sheet"),
        "inverter_nominal_ac_voltage": fv("inverter_nominal_ac_voltage", "240", "V", kind="inverter_spec_sheet"),
        "inverter_quantity": fv("inverter_quantity", "1"),
        "inverter_rated_ac_power": fv("inverter_rated_ac_power", "7.6", "kW", kind="inverter_spec_sheet"),
        "inverter_max_apparent_power": fv("inverter_max_apparent_power", "7.6", "kVA", kind="inverter_spec_sheet"),
        "inverter_max_continuous_output_current": fv("inverter_max_continuous_output_current", "32", "A", kind="inverter_spec_sheet"),
        "inverter_max_fault_current": fv("inverter_max_fault_current", "35.2", "A", kind="inverter_spec_sheet"),
        "inverter_phase_configuration": fv("inverter_phase_configuration", "single_phase_240v_split", kind="inverter_spec_sheet"),
        "export_intent": fv("export_intent", "export"),
        "tariff_program": fv("tariff_program", "NBT-1"),
        "applicant_name": fv("applicant_name", "Jordan Rivera"),
    }
    facts = [f for k, f in base.items() if k not in override]
    for key, value in override.items():
        if value:
            facts.append(fv(key, value, base[key].unit, base[key].document_kind))
    return facts


def test_clean_residential_packet_reconciles_to_a_complete_facility() -> None:
    rec = reconcile(residential(), DOCS, CIRCUIT, PRACTICE)
    f = rec.facility
    assert (f.gross_rating_kw, f.gross_rating_kva, f.exports, f.program) == (D("7.6"), D("7.6"), True, Program.NBT_1)
    assert f.short_circuit_pu == D("1.1") and f.equipment_certified is True
    assert (f.single_phase, f.on_240v_center_tap, f.phase_imbalance_kva) == (True, True, D(0))
    assert rec.findings == [] and rec.missing_documents == []
    # stated total and derived total agree, so both are recorded as sources of the same value
    derivations = [s.derivation for s in rec.provenance["gross_rating_kw"]]
    assert None in derivations and any(d and "1 × 7.6" in d for d in derivations)
    floor = disposition_floor(rec, run_initial_review(ScreenInputs(f, CIRCUIT, PRACTICE)).disposition_floor())
    assert floor is Disposition.INITIAL_REVIEW_PASS


def test_rounding_mismatch_that_changes_nothing_is_immaterial() -> None:
    facts = residential() + [fv("inverter_rated_ac_power", "7.68", "kW", kind="one_line_diagram")]
    rec = reconcile(facts, DOCS, CIRCUIT, PRACTICE)
    [finding] = rec.findings
    assert finding.field == "gross_rating_kw" and finding.material is False and finding.method is Method.RULE_OUTCOME
    assert "unchanged" in finding.rationale and "1.04%, within" in finding.rationale
    assert finding.chosen == D("7.68")  # conservative: larger value
    assert rec.applicant_blockers() == []


def test_large_conflict_is_material_even_when_no_screen_changes() -> None:
    facts = [f for f in residential() if f.field != "inverter_quantity"] + [
        fv("inverter_quantity", "1"), fv("inverter_quantity", "2", kind="one_line_diagram")]
    rec = reconcile(facts, DOCS, Circuit(networked_secondary=False, service_transformer_kva=D("100"),
                                         existing_gross_on_service_transformer_kva=D("0")), PRACTICE)
    [finding] = [f for f in rec.findings if f.field == "gross_rating_kw"]
    assert finding.material is True and "beyond the 2% rounding tolerance" in finding.rationale


def test_mismatch_that_crosses_30_kva_is_material_and_explained() -> None:
    facts = residential(system_apparent_power_rating="29.9", inverter_max_apparent_power="", inverter_quantity="") \
        + [fv("system_apparent_power_rating", "30.4", "kVA", kind="one_line_diagram")]
    rec = reconcile(facts, DOCS, CIRCUIT, PRACTICE)
    [finding] = [f for f in rec.findings if f.field == "gross_rating_kva"]
    assert finding.material is True and "Screen J: PASS with 29.9 → FAIL with 30.4" in finding.rationale
    assert finding.chosen == D("30.4")
    review = run_initial_review(ScreenInputs(rec.facility, CIRCUIT, PRACTICE))
    assert disposition_floor(rec, review.disposition_floor()) is Disposition.DEFICIENCY_NOTICE


def test_total_is_derived_from_quantity_and_per_unit_rating() -> None:
    facts = [f for f in residential() if f.field not in ("system_ac_rating", "inverter_quantity")] + [
        fv("inverter_quantity", "2")]
    rec = reconcile(facts, DOCS, CIRCUIT, PRACTICE)
    assert rec.facility.gross_rating_kw == D("15.2")
    assert "2 × 7.6" in rec.provenance["gross_rating_kw"][0].derivation


def test_no_total_without_a_stated_quantity() -> None:
    facts = [f for f in residential() if f.field not in ("system_ac_rating", "inverter_quantity")]
    assert reconcile(facts, DOCS, CIRCUIT, PRACTICE).facility.gross_rating_kw is None


def test_per_unit_short_circuit_uses_the_worst_inverter() -> None:
    facts = [f for f in residential() if not f.field.startswith("inverter_max")] + [
        fv("inverter_max_continuous_output_current", "32", "A", instance="Inverter 1"),
        fv("inverter_max_fault_current", "35.2", "A", instance="Inverter 1"),
        fv("inverter_max_continuous_output_current", "20", "A", instance="Inverter 2"),
        fv("inverter_max_fault_current", "30", "A", instance="Inverter 2"),
    ]
    assert reconcile(facts, DOCS, CIRCUIT, PRACTICE).facility.short_circuit_pu == D("1.5")


def test_unlisted_inverter_is_not_certified_and_near_matches_are_reported() -> None:
    rec = reconcile(residential(inverter_model="SE7600H-USX"), DOCS, CIRCUIT, PRACTICE)
    assert rec.facility.equipment_certified is False
    assert "SE7600H-US" in rec.equipment[0].near_matches


def test_missing_documents_are_applicant_blockers() -> None:
    rec = reconcile(residential(), ["application_form"], CIRCUIT, PRACTICE)
    assert rec.missing_documents == ["one_line_diagram", "inverter_spec_sheet"]
    assert disposition_floor(rec, Disposition.INITIAL_REVIEW_PASS) is Disposition.DEFICIENCY_NOTICE


def test_battery_facts_require_a_battery_spec_sheet() -> None:
    rec = reconcile(residential() + [fv("battery_model", "PW3")], DOCS, CIRCUIT, PRACTICE)
    assert "battery_spec_sheet" in rec.missing_documents


def test_formatting_differences_in_names_are_not_conflicts() -> None:
    facts = residential() + [fv("applicant_name", "JORDAN  RIVERA.", kind="one_line_diagram")]
    assert reconcile(facts, DOCS, CIRCUIT, PRACTICE).findings == []


def test_identity_conflicts_go_to_the_judge() -> None:
    seen = []

    def judge(findings, facts):
        seen.extend(findings)
        return [Judgment(True, "Different applicants: Jordan Rivera vs Sam Chen.")]

    facts = residential() + [fv("applicant_name", "Sam Chen", kind="one_line_diagram")]
    rec = reconcile(facts, DOCS, CIRCUIT, PRACTICE, judge=judge)
    [finding] = rec.findings
    assert seen and finding.method is Method.LLM and finding.material is True
    assert disposition_floor(rec, Disposition.INITIAL_REVIEW_PASS) is Disposition.DEFICIENCY_NOTICE


def test_without_a_judge_identity_conflicts_stay_unjudged_and_route_to_an_engineer() -> None:
    facts = residential() + [fv("applicant_name", "Sam Chen", kind="one_line_diagram")]
    rec = reconcile(facts, DOCS, CIRCUIT, PRACTICE)
    assert rec.unjudged() and rec.findings[0].material is None
    assert disposition_floor(rec, Disposition.INITIAL_REVIEW_PASS) is Disposition.NEEDS_ENGINEER_DETERMINATION


@pytest.mark.parametrize(("config", "service_v", "center_tap", "imbalance"), [
    ("single_phase_120v", "240", True, D("7.6")),
    ("three_phase", None, False, None),
])
def test_phase_configuration_drives_screen_e_inputs(config, service_v, center_tap, imbalance) -> None:
    facts = residential(inverter_phase_configuration=config)
    if service_v:
        facts += [fv("service_voltage", service_v, "V"), fv("service_phases", "1")]
    f = reconcile(facts, DOCS, CIRCUIT, PRACTICE).facility
    assert (f.on_240v_center_tap, f.phase_imbalance_kva) == (center_tap, imbalance)
