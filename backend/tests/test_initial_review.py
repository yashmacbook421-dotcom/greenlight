"""Rule 21 Initial Review engine: thresholds to the digit, routing, and missing-data behaviour."""

from dataclasses import replace
from decimal import Decimal as D

import pytest

from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.screens.initial_review import run_initial_review
from app.domains.interconnection.screens.types import (
    Blocker,
    Circuit,
    Classification,
    Facility,
    InterconnectionType,
    PrimaryLineType,
    Program,
    ProtectiveDevice,
    ScreenInputs,
    Status,
    UtilityPractice,
)

ORDER = ["A", "B", "C", "D", "E", "F", "F1", "G", "H", "I", "J", "K", "L", "M"]
PRACTICE = UtilityPractice(source="synthetic, for tests", d_transformer_rating_multiplier=D("1.0"),
                           e_max_phase_imbalance_kva=D("5"))

# A typical rooftop system: 7.6 kW / 7.6 kVA, 240 V split-phase inverter, exporting under NBT.
RESIDENTIAL = ScreenInputs(
    facility=Facility(gross_rating_kva=D("7.6"), gross_rating_kw=D("7.6"), inverter_based=True,
                      starts_by_motoring=False, equipment_certified=True, single_phase=True,
                      on_240v_center_tap=True, phase_imbalance_kva=D("0"), exports=True, program=Program.NBT_1,
                      short_circuit_pu=D("1.1")),
    circuit=Circuit(networked_secondary=False, service_transformer_kva=D("25"),
                    existing_gross_on_service_transformer_kva=D("6")),
    practice=PRACTICE,
)

# A 250 kW / 260 kVA three-phase commercial rooftop system on a four-wire feeder with ICA data.
COMMERCIAL = ScreenInputs(
    facility=Facility(gross_rating_kva=D("260"), gross_rating_kw=D("250"), inverter_based=True,
                      starts_by_motoring=False, equipment_certified=True, single_phase=False,
                      on_240v_center_tap=False, exports=True, program=Program.NEM_2, short_circuit_pu=D("1.1")),
    circuit=Circuit(networked_secondary=False, service_transformer_kva=D("500"),
                    existing_gross_on_service_transformer_kva=D("0"), existing_sccr_sum=D("0.02"),
                    facility_short_circuit_contribution_hv_a=D("30"), utility_short_circuit_contribution_hv_a=D("1000"),
                    protective_devices=(ProtectiveDevice("breaker-1", D("12000"), D("8000")),
                                        ProtectiveDevice("recloser-7", D("8000"), D("5000"))),
                    facility_fault_contribution_a=D("300"),
                    primary_line_type=PrimaryLineType.THREE_PHASE_FOUR_WIRE, interconnection_type=InterconnectionType.OTHER,
                    line_section_peak_load_kw=D("4000"), existing_gen_on_line_section_kw=D("100"),
                    known_stability_limitation=False, transmission_interdependency=False, islanding_possible=False,
                    ground_fault_overvoltage_possible=False, ica_sg_min_kw=D("600"), ica_of_min_kw=D("900")),
    practice=PRACTICE,
)


def fac(base: ScreenInputs, **kw) -> ScreenInputs:
    return replace(base, facility=replace(base.facility, **kw))


def cir(base: ScreenInputs, **kw) -> ScreenInputs:
    return replace(base, circuit=replace(base.circuit, **kw))


def statuses(x: ScreenInputs) -> dict[str, str]:
    return {r.screen: r.status.value for r in run_initial_review(x).results}


# --- whole-flow scenarios -------------------------------------------------------------

def test_residential_rooftop_runs_the_short_path() -> None:
    review = run_initial_review(RESIDENTIAL)
    assert [r.screen for r in review.results] == ORDER
    assert statuses(RESIDENTIAL) == {
        "A": "PASS", "B": "PASS", "C": "NOT_APPLICABLE", "D": "PASS", "E": "PASS", "F": "NOT_APPLICABLE",
        "F1": "PASS", "G": "NOT_APPLICABLE", "H": "NOT_APPLICABLE", "I": "PASS", "J": "PASS",
        "K": "SKIPPED", "L": "SKIPPED", "M": "SKIPPED",
    }
    assert review.disposition_floor() is Disposition.INITIAL_REVIEW_PASS


def test_commercial_system_runs_the_long_path() -> None:
    review = run_initial_review(COMMERCIAL)
    s = statuses(COMMERCIAL)
    assert s["J"] == "FAIL" and review.by_screen()["J"].classification is Classification.ROUTING
    assert s["K"] == "PASS" and s["L"] == "SKIPPED"
    assert {k: s[k] for k in ("F", "F1", "G", "H", "M")} == dict.fromkeys(("F", "F1", "G", "H", "M"), "PASS")
    assert review.disposition_floor() is Disposition.INITIAL_REVIEW_PASS


def test_every_result_satisfies_the_database_invariants() -> None:
    scenarios = [RESIDENTIAL, COMMERCIAL, fac(RESIDENTIAL, gross_rating_kva=None), fac(COMMERCIAL, exports=None),
                 cir(COMMERCIAL, known_stability_limitation=None), fac(RESIDENTIAL, exports=False, export_option=1),
                 replace(RESIDENTIAL, practice=None), fac(COMMERCIAL, program=Program.OTHER)]
    for x in scenarios:
        results = run_initial_review(x).results
        assert [r.screen for r in results] == ORDER
        for r in results:
            if r.status is not Status.INCONCLUSIVE:
                assert r.citations, r
            if r.status is Status.FAIL:
                assert r.classification is not None, r
            if r.status is Status.INCONCLUSIVE:
                assert r.reason and r.blocker is not None, r
            if r.status is Status.SKIPPED:
                assert r.routed_by, r


# --- thresholds, to the digit ---------------------------------------------------------

@pytest.mark.parametrize(("kva", "j", "k_path"), [("30", "PASS", "SKIPPED"), ("30.01", "FAIL", "PASS")])
def test_screen_j_boundary_reroutes_k_to_m(kva: str, j: str, k_path: str) -> None:
    x = fac(COMMERCIAL, gross_rating_kva=D(kva), gross_rating_kw=D(kva))
    s = statuses(x)
    assert (s["J"], s["K"]) == (j, k_path)


def test_rounding_that_crosses_30_kva_changes_what_the_review_needs() -> None:
    """29.9 vs 30.4: the same house, but only one reading needs line-section data."""
    house = cir(RESIDENTIAL, service_transformer_kva=D("50"))  # big enough that Screen D passes either way
    under = run_initial_review(fac(house, gross_rating_kva=D("29.9"), gross_rating_kw=D("29.9")))
    over = run_initial_review(fac(house, gross_rating_kva=D("30.4"), gross_rating_kw=D("29.9")))
    assert under.disposition_floor() is Disposition.INITIAL_REVIEW_PASS
    assert over.disposition_floor() is Disposition.NEEDS_ENGINEER_DETERMINATION
    assert over.by_screen()["M"].missing_inputs == ("circuit.existing_gen_on_line_section_kw",
                                                    "circuit.line_section_peak_load_kw")


@pytest.mark.parametrize("screen", ["F", "G", "H"])
def test_size_exclusion_is_inclusive_at_30_kva(screen: str) -> None:
    assert statuses(fac(COMMERCIAL, gross_rating_kva=D("30")))[screen] == "NOT_APPLICABLE"
    assert statuses(fac(COMMERCIAL, gross_rating_kva=D("30.001")))[screen] != "NOT_APPLICABLE"


@pytest.mark.parametrize(("facility_a", "status"), [("80", "PASS"), ("80.001", "FAIL")])
def test_screen_f_sccr_sum_limit_is_inclusive(facility_a: str, status: str) -> None:
    r = run_initial_review(cir(COMMERCIAL, facility_short_circuit_contribution_hv_a=D(facility_a))).by_screen()["F"]
    assert r.status.value == status
    assert r.computed == D("0.02") + D(facility_a) / D("1000")
    if status == "FAIL":
        assert r.classification is Classification.MITIGABLE_IN_INITIAL_REVIEW


@pytest.mark.parametrize(("pu", "ica", "status"), [
    ("1.2", None, "PASS"),            # first condition, inclusive
    ("1.3", "300", "PASS"),           # 250 * 1.3 = 325 < 300 * 1.2 = 360
    ("1.44", "300", "FAIL"),          # 250 * 1.44 = 360, not strictly less than 360
    ("1.3", None, "INCONCLUSIVE"),    # second condition needs the Protection ICA value
])
def test_screen_f1(pu: str, ica: str | None, status: str) -> None:
    x = cir(fac(COMMERCIAL, short_circuit_pu=D(pu)), protection_ica_kw=D(ica) if ica else None)
    r = run_initial_review(x).by_screen()["F1"]
    assert r.status.value == status
    if status == "INCONCLUSIVE":
        assert r.blocker is Blocker.UTILITY and r.missing_inputs == ("circuit.protection_ica_kw",)


@pytest.mark.parametrize(("contribution", "status"), [("2500", "PASS"), ("2500.01", "FAIL")])
def test_screen_g_87_5_percent_is_inclusive(contribution: str, status: str) -> None:
    # breaker-1: (8000 + 2500) / 12000 = 0.875 exactly; recloser-7: (5000 + 2500) / 8000 = 0.9375 → would fail
    x = cir(COMMERCIAL, facility_fault_contribution_a=D(contribution),
            protective_devices=(ProtectiveDevice("breaker-1", D("12000"), D("8000")),))
    r = run_initial_review(x).by_screen()["G"]
    assert (r.status.value, r.threshold) == (status, D("0.875"))


def test_screen_g_reports_the_worst_device() -> None:
    r = run_initial_review(cir(COMMERCIAL, facility_fault_contribution_a=D("2500"))).by_screen()["G"]
    assert r.status is Status.FAIL and "recloser-7" in r.reason and r.computed == D("0.9375")


@pytest.mark.parametrize(("line", "itype", "existing", "status"), [
    (PrimaryLineType.THREE_PHASE_THREE_WIRE, InterconnectionType.OTHER, "99999", "PASS"),
    (PrimaryLineType.THREE_PHASE_FOUR_WIRE, InterconnectionType.SINGLE_PHASE_LINE_TO_NEUTRAL, "99999", "PASS"),
    (PrimaryLineType.THREE_PHASE_FOUR_WIRE, InterconnectionType.OTHER, "150", "PASS"),    # 250 + 150 = 400 = 10% of 4000
    (PrimaryLineType.MIXED, InterconnectionType.OTHER, "150.01", "FAIL"),
])
def test_screen_h_table_g1(line, itype, existing: str, status: str) -> None:
    x = cir(COMMERCIAL, primary_line_type=line, interconnection_type=itype, existing_gen_on_line_section_kw=D(existing))
    assert statuses(x)["H"] == status


@pytest.mark.parametrize(("program", "kw", "l_status"), [
    (Program.NEM_2, "500", "SKIPPED"), (Program.NBT_1, "500.01", "PASS"), (Program.OTHER, "250", "PASS"),
])
def test_screen_k_gates_screen_l(program: Program, kw: str, l_status: str) -> None:
    assert statuses(fac(COMMERCIAL, program=program, gross_rating_kw=D(kw)))["L"] == l_status


def test_screen_l_any_raised_condition_fails_even_if_others_unknown() -> None:
    x = cir(fac(COMMERCIAL, program=Program.OTHER), islanding_possible=True, transmission_interdependency=None)
    r = run_initial_review(x).by_screen()["L"]
    assert r.status is Status.FAIL and r.classification is Classification.SUPPLEMENTAL_REQUIRED


def test_screen_l_unknown_conditions_are_the_utilitys_to_supply() -> None:
    r = run_initial_review(cir(fac(COMMERCIAL, program=Program.OTHER), islanding_possible=None)).by_screen()["L"]
    assert (r.status, r.blocker, r.missing_inputs) == (Status.INCONCLUSIVE, Blocker.UTILITY, ("circuit.islanding_possible",))


def test_screen_m_uses_the_lower_of_both_ica_values() -> None:
    # 0.9 * 277.78 = 250.002 >= 250 kW → pass, whichever of SG/OF is the lower one
    ok = run_initial_review(cir(COMMERCIAL, ica_sg_min_kw=D("900"), ica_of_min_kw=D("277.78"))).by_screen()["M"]
    assert ok.status is Status.PASS and ok.threshold == D("250.002")
    # 0.9 * 277.77 = 249.993 < 250 kW → fail
    bad = run_initial_review(cir(COMMERCIAL, ica_sg_min_kw=D("277.77"), ica_of_min_kw=D("900"))).by_screen()["M"]
    assert bad.status is Status.FAIL and bad.classification is Classification.SUPPLEMENTAL_REQUIRED


def test_screen_m_falls_back_to_15_percent_without_ica_and_the_limit_is_strict() -> None:
    at_limit = cir(COMMERCIAL, ica_sg_min_kw=None, ica_of_min_kw=None, existing_gen_on_line_section_kw=D("350"))
    assert run_initial_review(at_limit).by_screen()["M"].status is Status.FAIL  # 600 is not < 0.15 * 4000
    below = cir(at_limit, existing_gen_on_line_section_kw=D("349.99"))
    assert run_initial_review(below).by_screen()["M"].status is Status.PASS


def test_screen_m_with_only_one_ica_value_is_not_silently_downgraded_to_the_fallback() -> None:
    r = run_initial_review(cir(COMMERCIAL, ica_of_min_kw=None)).by_screen()["M"]
    assert r.status is Status.INCONCLUSIVE and r.missing_inputs == ("circuit.ica_of_min_kw",)


# --- Screen A ---------------------------------------------------------------------------

@pytest.mark.parametrize(("max_load", "existing", "inverter", "status"), [
    ("400", "10", True, "PASS"),        # min(20, 50) = 20; 7.6 + 10 = 17.6
    ("400", "12.4", True, "PASS"),      # exactly 20
    ("400", "12.41", True, "FAIL"),
    ("4000", "42.4", True, "PASS"),     # min(200, 50) = 50; 7.6 + 42.4 = 50
    ("4000", "10", False, "FAIL"),      # exception requires inverter-based equipment
])
def test_screen_a_spot_network_exception(max_load: str, existing: str, inverter: bool, status: str) -> None:
    x = cir(fac(RESIDENTIAL, inverter_based=inverter), networked_secondary=True, spot_network=True,
            spot_network_max_load_kw=D(max_load), existing_inverter_gen_on_spot_network_kw=D(existing))
    r = run_initial_review(x).by_screen()["A"]
    assert r.status.value == status
    if status == "FAIL":
        assert r.classification is Classification.SUPPLEMENTAL_REQUIRED


def test_screen_a_grid_network_fails() -> None:
    assert statuses(cir(RESIDENTIAL, networked_secondary=True, spot_network=False))["A"] == "FAIL"


# --- Screens B, D, E ----------------------------------------------------------------------

def test_uncertified_equipment_fails_b_and_requires_supplemental() -> None:
    review = run_initial_review(fac(RESIDENTIAL, equipment_certified=False))
    assert review.by_screen()["B"].classification is Classification.MITIGABLE_IN_INITIAL_REVIEW
    assert review.disposition_floor() is Disposition.SUPPLEMENTAL_REVIEW_REQUIRED


@pytest.mark.parametrize(("existing", "conductor", "status"), [
    ("17.4", None, "PASS"),   # 7.6 + 17.4 = 25 = rating
    ("17.41", None, "FAIL"),
    ("10", "15", "FAIL"),     # conductor rating is the binding limit
])
def test_screen_d(existing: str, conductor: str | None, status: str) -> None:
    x = cir(RESIDENTIAL, existing_gross_on_service_transformer_kva=D(existing),
            secondary_conductor_rating_kva=D(conductor) if conductor else None)
    assert statuses(x)["D"] == status


def test_screens_d_and_e_never_invent_utility_practice() -> None:
    review = run_initial_review(replace(RESIDENTIAL, practice=None))
    d, e = review.by_screen()["D"], review.by_screen()["E"]
    assert d.status is e.status is Status.INCONCLUSIVE
    assert d.blocker is e.blocker is Blocker.UTILITY
    assert review.disposition_floor() is Disposition.NEEDS_ENGINEER_DETERMINATION


def test_screen_e_only_applies_to_single_phase_center_tap() -> None:
    assert statuses(fac(RESIDENTIAL, on_240v_center_tap=False))["E"] == "NOT_APPLICABLE"
    assert statuses(fac(RESIDENTIAL, phase_imbalance_kva=D("5.01")))["E"] == "FAIL"


# --- Screen I routing ------------------------------------------------------------------------

def test_non_export_skips_j_through_m() -> None:
    s = statuses(fac(COMMERCIAL, exports=False, export_option=1))
    assert s["I"] == "PASS" and [s[k] for k in "JKLM"] == ["SKIPPED"] * 4


OPTION_3 = fac(RESIDENTIAL, exports=False, export_option=3, service_equipment_amps=D("200"),
               service_voltage_v=D("240"), service_phases=1, certified_non_islanding=True)
OPTION_3 = cir(OPTION_3, customer_primary_service=False)


def test_option_3_all_conditions_met() -> None:
    # (a) 7.6 <= 0.25 * 48 = 12;  (b) 7.6 <= 0.5 * 25 = 12.5;  (c) certified
    assert statuses(OPTION_3)["I"] == "PASS"


@pytest.mark.parametrize(("change", "fragment"), [
    ({"facility": {"service_equipment_amps": D("100")}}, "(a)"),            # 0.25 * 24 = 6 < 7.6
    ({"circuit": {"service_transformer_kva": D("15")}}, "(b)"),             # 0.5 * 15 = 7.5 < 7.6
    ({"facility": {"certified_non_islanding": False}}, "(c)"),
])
def test_option_3_unmet_condition_is_an_applicant_deficiency(change: dict, fragment: str) -> None:
    x = fac(OPTION_3, **change.get("facility", {}))
    x = cir(x, **change.get("circuit", {}))
    review = run_initial_review(x)
    i = review.by_screen()["I"]
    assert (i.status, i.blocker) == (Status.INCONCLUSIVE, Blocker.APPLICANT) and fragment in i.reason
    assert review.disposition_floor() is Disposition.DEFICIENCY_NOTICE


def test_option_3_transformer_condition_waived_for_primary_service() -> None:
    assert statuses(cir(OPTION_3, customer_primary_service=True, service_transformer_kva=D("1")))["I"] == "PASS"


def test_option_3_three_phase_service_uses_root_three() -> None:
    # 208 V * 100 A * sqrt(3) / 1000 = 36.03 kVA; 25% = 9.007 ≥ 7.6
    assert statuses(fac(OPTION_3, service_voltage_v=D("208"), service_equipment_amps=D("100"), service_phases=3))["I"] == "PASS"


@pytest.mark.parametrize(("host", "status"), [("15.2", "PASS"), ("15.19", "INCONCLUSIVE")])
def test_option_4_host_load(host: str, status: str) -> None:
    x = fac(RESIDENTIAL, exports=False, export_option=4, min_host_load_kw_12mo=D(host))
    assert statuses(x)["I"] == status


@pytest.mark.parametrize(("exports", "option", "blocker"), [
    (True, 5, Blocker.UTILITY),       # limited export: out of scope, engineer
    (True, 2, Blocker.APPLICANT),     # contradiction in the application
    (False, None, Blocker.APPLICANT), # non-export without an option
    (False, 8, Blocker.UTILITY),      # §Mm1: out of scope
])
def test_screen_i_cannot_route(exports: bool, option: int | None, blocker: Blocker) -> None:
    review = run_initial_review(fac(COMMERCIAL, exports=exports, export_option=option))
    by = review.by_screen()
    assert by["I"].status is Status.INCONCLUSIVE and by["I"].blocker is blocker
    assert all(by[s].status is Status.INCONCLUSIVE and by[s].routed_by == "I" for s in "JKLM")


# --- dispositions, determinism, synthetic data --------------------------------------------------

def test_applicant_deficiency_outranks_screen_failure() -> None:
    x = fac(RESIDENTIAL, equipment_certified=False, gross_rating_kva=None)
    assert run_initial_review(x).disposition_floor() is Disposition.DEFICIENCY_NOTICE


def test_same_inputs_same_results_and_hash() -> None:
    a, b = run_initial_review(COMMERCIAL), run_initial_review(COMMERCIAL)
    assert a == b and a.input_hash == b.input_hash and len(a.input_hash) == 64


def test_any_input_change_changes_the_hash() -> None:
    assert run_initial_review(COMMERCIAL).input_hash != run_initial_review(
        cir(COMMERCIAL, existing_sccr_sum=D("0.021"))).input_hash


def test_synthetic_circuit_fields_are_carried_onto_results() -> None:
    x = cir(RESIDENTIAL, synthetic_fields=frozenset({"service_transformer_kva"}))
    by = run_initial_review(x).by_screen()
    assert by["D"].synthetic_inputs == ("circuit.service_transformer_kva",)
    assert by["B"].synthetic_inputs == ()
