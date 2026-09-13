from app.core.guardrails import (
    citation_validity,
    disposition_veto,
    number_faithfulness,
    numbers_in,
    provenance_completeness,
)

EVIDENCE = ['{"screen": "J", "computed": "30.4", "threshold": "30", "reason": "above 30 kVA"}',
            '{"screen": "G", "threshold": "0.875", "computed": "7680"}']
SECTIONS = {151: {"G.1.j", "G.1.k"}, 70: {"E.5", "E.5.a", "E.5.b", "E.5.b.i"}}
KNOWN = {s for v in SECTIONS.values() for s in v}


def test_identifiers_are_not_treated_as_quantities() -> None:
    text = ("Under Rule 21 §G.1.j (Sheet 151), Screen F1 and UL 1741 SB, NBT-1, ICA-SG 576, model SE7600H-US:\n"
            "1. The gross rating is 30.4 kVA.")
    assert numbers_in(text) == [("30.4", False)]


def test_supported_numbers_pass_including_thousands_and_percent() -> None:
    assert number_faithfulness("Rated 7,680 W; limit 87.5% of capability; 30.4 kVA exceeds 30 kVA.", EVIDENCE).passed


def test_invented_number_fails_and_is_named() -> None:
    v = number_faithfulness("The facility is 31.2 kVA, above the 30 kVA limit.", EVIDENCE)
    assert not v.passed and v.data["unsupported"] == ["31.2"]


def test_valid_citations_pass() -> None:
    letter = "See Rule 21 §G.1.j (Sheet 151) and §E.5.b.i, Sheet 70."
    v = citation_validity(letter, lambda s: SECTIONS.get(s, set()), KNOWN)
    assert v.passed and len(v.data["cited"]) == 2


def test_parent_section_on_a_sheet_is_accepted() -> None:
    assert citation_validity("Per §E.5 (Sheet 70)", lambda s: SECTIONS.get(s, set()), KNOWN).passed


def test_nonexistent_section_and_wrong_sheet_fail() -> None:
    v = citation_validity("Per §G.9.z (Sheet 151) and §G.1.j (Sheet 70) and Sheet 999.",
                          lambda s: SECTIONS.get(s, set()), KNOWN)
    assert not v.passed
    assert v.data["invalid"] == ["§G.9.z does not exist in the pinned rules", "§G.1.j is not on Sheet 70",
                                 "Sheet 999 is not in the pinned rules"]


def test_veto_overrides_a_too_lenient_disposition() -> None:
    severity = {"PASS": 0, "DEFICIENCY": 3}
    final, v = disposition_veto("PASS", "DEFICIENCY", severity)
    assert final == "DEFICIENCY" and not v.passed
    final, v = disposition_veto("DEFICIENCY", "PASS", severity)
    assert final == "DEFICIENCY" and v.passed


def test_unsourced_items_are_stripped() -> None:
    items = [{"basis_kind": "screen", "basis_ref": "J"}, {"basis_kind": "fact", "basis_ref": "made-up"}]
    kept, v = provenance_completeness(items, lambda k, r: r == "J")
    assert kept == items[:1] and not v.passed


def test_rounded_presentation_of_a_long_evidence_value_is_accepted_and_recorded() -> None:
    evidence = ['{"short_circuit_pu": "1.117924528301886792452830189", "computed": "30.4"}']
    v = number_faithfulness("Per-unit contribution of approximately 1.12.", evidence)
    assert v.passed and v.data["rounded"] == {"1.12": "1.117924528301886792452830189"}


def test_rounding_cannot_hide_a_threshold_crossing_or_invent_digits() -> None:
    evidence = ['{"computed": "30.4", "short_circuit_pu": "1.117924528301886792452830189"}']
    assert not number_faithfulness("The facility is 30 kVA.", evidence).passed       # 0 decimals: never rounded
    assert not number_faithfulness("Contribution of 1.18.", evidence).passed          # does not round from evidence
    assert not number_faithfulness("Rating 30.40 kVA and 30.4.", ['{"x": "30.4"}']).data.get("rounded")
