"""PG&E Electric Rule 21 §G.1 Initial Review, Screens A–M, as the tariff's flowchart.

Pure functions of ScreenInputs. No I/O, no clock, no model: the same inputs
produce the same results, byte for byte.
"""

import hashlib
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, replace
from decimal import Decimal

from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.screens import rulebook as rb
from app.domains.interconnection.screens.types import (
    Blocker,
    Classification,
    InterconnectionType,
    PrimaryLineType,
    Program,
    ScreenInputs,
    ScreenResult,
    Status,
)

SQRT3 = Decimal(3).sqrt()


# --- helpers --------------------------------------------------------------------

def _fmt(value: object) -> str:
    return format(value, "f") if isinstance(value, Decimal) else str(value)


def _missing(screen: str, citations: tuple[rb.Citation, ...], reason: str, **named: object) -> ScreenResult | None:
    """INCONCLUSIVE if any named input is None. Keys look like 'facility.gross_rating_kw'."""
    absent = tuple(k.replace("__", ".") for k, v in named.items() if v is None)
    if not absent:
        return None
    blocker = Blocker.APPLICANT if any(k.startswith("facility.") for k in absent) else Blocker.UTILITY
    present = {k.replace("__", "."): _fmt(v) for k, v in named.items() if v is not None}
    return ScreenResult(screen, Status.INCONCLUSIVE, citations, inputs=present, missing_inputs=absent,
                        blocker=blocker, reason=f"{reason}: missing {', '.join(absent)}")


def _decided(screen: str, ok: bool, citations: tuple[rb.Citation, ...], *, fail_as: Classification,
             inputs: dict[str, object], formula: str, computed: Decimal | None, threshold: Decimal | None,
             reason: str) -> ScreenResult:
    return ScreenResult(
        screen, Status.PASS if ok else Status.FAIL, citations,
        inputs={k: _fmt(v) for k, v in inputs.items()}, formula=formula, computed=computed, threshold=threshold,
        classification=None if ok else fail_as, reason=reason,
    )


def _not_applicable_by_size(screen: str, rule: rb.Threshold, x: ScreenInputs) -> ScreenResult | None:
    """For F, G, H: NOT_APPLICABLE at ≤ 30 kVA; INCONCLUSIVE if the rating is unknown; None to proceed."""
    kva = x.facility.gross_rating_kva
    if kva is None:
        return _missing(screen, (rule.citation,), "size exclusion cannot be evaluated",
                        facility__gross_rating_kva=None)
    if kva <= rule.value:
        return ScreenResult(screen, Status.NOT_APPLICABLE, (rule.citation,),
                            inputs={"facility.gross_rating_kva": _fmt(kva)},
                            formula="gross_rating_kva <= 30", computed=kva, threshold=rule.value,
                            reason=f"gross rating {_fmt(kva)} kVA is {_fmt(rule.value)} kVA or less")
    return None


# --- Screens A–H ----------------------------------------------------------------

def screen_a(x: ScreenInputs) -> ScreenResult:
    f, c = x.facility, x.circuit
    cites = (rb.A_QUESTION, rb.A_FAIL)
    if r := _missing("A", cites, "network status unknown", circuit__networked_secondary=c.networked_secondary):
        return r
    if not c.networked_secondary:
        return _decided("A", True, cites, fail_as=Classification.SUPPLEMENTAL_REQUIRED,
                        inputs={"circuit.networked_secondary": False}, formula="networked_secondary == false",
                        computed=None, threshold=None, reason="PCC is not on a networked secondary system")
    cites = (*cites, rb.A_SPOT_INVERTER, rb.A_SPOT_MAX_FRACTION.citation)
    if r := _missing("A", cites, "spot network exception cannot be evaluated",
                     circuit__spot_network=c.spot_network):
        return r
    if not c.spot_network:
        return _decided("A", False, cites, fail_as=Classification.SUPPLEMENTAL_REQUIRED,
                        inputs={"circuit.networked_secondary": True, "circuit.spot_network": False},
                        formula="networked_secondary == false", computed=None, threshold=None,
                        reason="PCC is on a networked secondary system that is not a spot network")
    if r := _missing("A", cites, "spot network exception cannot be evaluated",
                     facility__inverter_based=f.inverter_based, facility__gross_rating_kw=f.gross_rating_kw,
                     circuit__spot_network_max_load_kw=c.spot_network_max_load_kw,
                     circuit__existing_inverter_gen_on_spot_network_kw=c.existing_inverter_gen_on_spot_network_kw):
        return r
    aggregate = f.gross_rating_kw + c.existing_inverter_gen_on_spot_network_kw
    limit = min(rb.A_SPOT_MAX_FRACTION.value * c.spot_network_max_load_kw, rb.A_SPOT_MAX_KW.value)
    ok = bool(f.inverter_based) and aggregate <= limit
    return _decided(
        "A", ok, cites, fail_as=Classification.SUPPLEMENTAL_REQUIRED,
        inputs={"facility.inverter_based": f.inverter_based, "facility.gross_rating_kw": f.gross_rating_kw,
                "circuit.spot_network_max_load_kw": c.spot_network_max_load_kw,
                "circuit.existing_inverter_gen_on_spot_network_kw": c.existing_inverter_gen_on_spot_network_kw},
        formula="inverter_based and (gross_rating_kw + existing_inverter_gen_on_spot_network_kw) "
                "<= min(0.05 * spot_network_max_load_kw, 50)",
        computed=aggregate, threshold=limit,
        reason=("spot network exception met" if ok else
                "spot network exception not met" + ("" if f.inverter_based else ": facility is not inverter-based")),
    )


def screen_b(x: ScreenInputs) -> ScreenResult:
    f = x.facility
    cites = (rb.B_QUESTION, rb.QUICK_REVIEW_A_TO_H)
    if r := _missing("B", cites, "certification status unknown", facility__equipment_certified=f.equipment_certified):
        return r
    return _decided("B", bool(f.equipment_certified), cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW,
                    inputs={"facility.equipment_certified": f.equipment_certified},
                    formula="equipment_certified == true", computed=None, threshold=None,
                    reason="equipment is certified" if f.equipment_certified else "equipment is not certified")


def screen_c(x: ScreenInputs) -> ScreenResult:
    f = x.facility
    cites = (rb.C_APPLICABILITY,)
    if f.starts_by_motoring is False or (f.starts_by_motoring is None and f.inverter_based is True):
        return ScreenResult("C", Status.NOT_APPLICABLE, cites,
                            inputs={"facility.starts_by_motoring": _fmt(f.starts_by_motoring),
                                    "facility.inverter_based": _fmt(f.inverter_based)},
                            reason="generating facility does not start by motoring")
    if f.starts_by_motoring:
        return ScreenResult("C", Status.INCONCLUSIVE, cites, inputs={"facility.starts_by_motoring": "True"},
                            blocker=Blocker.UTILITY,
                            reason="starting voltage drop for motoring generators is outside Greenlight's scope")
    return _missing("C", cites, "applicability unknown",  # type: ignore[return-value]
                    facility__starts_by_motoring=f.starts_by_motoring, facility__inverter_based=f.inverter_based)


def screen_d(x: ScreenInputs) -> ScreenResult:
    f, c, p = x.facility, x.circuit, x.practice
    cites = (rb.D_QUESTION, rb.QUICK_REVIEW_A_TO_H)
    if r := _missing("D", cites, "transformer loading cannot be evaluated",
                     facility__gross_rating_kva=f.gross_rating_kva,
                     circuit__service_transformer_kva=c.service_transformer_kva,
                     circuit__existing_gross_on_service_transformer_kva=c.existing_gross_on_service_transformer_kva,
                     practice__d_transformer_rating_multiplier=p.d_transformer_rating_multiplier if p else None):
        return r
    aggregate = f.gross_rating_kva + c.existing_gross_on_service_transformer_kva
    limit = c.service_transformer_kva * p.d_transformer_rating_multiplier
    inputs: dict[str, object] = {
        "facility.gross_rating_kva": f.gross_rating_kva, "circuit.service_transformer_kva": c.service_transformer_kva,
        "circuit.existing_gross_on_service_transformer_kva": c.existing_gross_on_service_transformer_kva,
        "practice.d_transformer_rating_multiplier": p.d_transformer_rating_multiplier, "practice.source": p.source,
    }
    formula = "gross_rating_kva + existing_gross_on_service_transformer_kva <= service_transformer_kva * multiplier"
    if c.secondary_conductor_rating_kva is not None:
        limit = min(limit, c.secondary_conductor_rating_kva * p.d_transformer_rating_multiplier)
        inputs["circuit.secondary_conductor_rating_kva"] = c.secondary_conductor_rating_kva
        formula += " and <= secondary_conductor_rating_kva * multiplier"
    ok = aggregate <= limit
    return _decided("D", ok, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW, inputs=inputs,
                    formula=formula, computed=aggregate, threshold=limit,
                    reason=f"aggregate {_fmt(aggregate)} kVA {'within' if ok else 'exceeds'} {_fmt(limit)} kVA")


def screen_e(x: ScreenInputs) -> ScreenResult:
    f, p = x.facility, x.practice
    cites = (rb.E_QUESTION, rb.QUICK_REVIEW_A_TO_H)
    if r := _missing("E", cites, "applicability unknown",
                     facility__single_phase=f.single_phase, facility__on_240v_center_tap=f.on_240v_center_tap):
        return r
    if not (f.single_phase and f.on_240v_center_tap):
        return ScreenResult("E", Status.NOT_APPLICABLE, cites,
                            inputs={"facility.single_phase": _fmt(f.single_phase),
                                    "facility.on_240v_center_tap": _fmt(f.on_240v_center_tap)},
                            reason="not a single-phase generator on a 240 V center-tap service")
    if r := _missing("E", cites, "imbalance cannot be evaluated",
                     facility__phase_imbalance_kva=f.phase_imbalance_kva,
                     practice__e_max_phase_imbalance_kva=p.e_max_phase_imbalance_kva if p else None):
        return r
    ok = f.phase_imbalance_kva <= p.e_max_phase_imbalance_kva
    return _decided("E", ok, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW,
                    inputs={"facility.phase_imbalance_kva": f.phase_imbalance_kva,
                            "practice.e_max_phase_imbalance_kva": p.e_max_phase_imbalance_kva,
                            "practice.source": p.source},
                    formula="phase_imbalance_kva <= e_max_phase_imbalance_kva",
                    computed=f.phase_imbalance_kva, threshold=p.e_max_phase_imbalance_kva,
                    reason=f"imbalance {_fmt(f.phase_imbalance_kva)} kVA "
                           f"{'within' if ok else 'exceeds'} {_fmt(p.e_max_phase_imbalance_kva)} kVA")


def screen_f(x: ScreenInputs) -> ScreenResult:
    if r := _not_applicable_by_size("F", rb.F_NOT_APPLICABLE_KVA, x):
        return r
    c = x.circuit
    cites = (rb.F_SCCR_MAX.citation, rb.SCCR_DEFINITION, rb.QUICK_REVIEW_A_TO_H)
    if r := _missing("F", cites, "short circuit contribution ratio cannot be computed",
                     circuit__facility_short_circuit_contribution_hv_a=c.facility_short_circuit_contribution_hv_a,
                     circuit__utility_short_circuit_contribution_hv_a=c.utility_short_circuit_contribution_hv_a,
                     circuit__existing_sccr_sum=c.existing_sccr_sum):
        return r
    if c.utility_short_circuit_contribution_hv_a <= 0:
        return ScreenResult("F", Status.INCONCLUSIVE, cites, blocker=Blocker.UTILITY,
                            inputs={"circuit.utility_short_circuit_contribution_hv_a":
                                    _fmt(c.utility_short_circuit_contribution_hv_a)},
                            reason="utility short circuit contribution must be positive")
    total = c.existing_sccr_sum + c.facility_short_circuit_contribution_hv_a / c.utility_short_circuit_contribution_hv_a
    ok = total <= rb.F_SCCR_MAX.value
    return _decided("F", ok, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW,
                    inputs={"circuit.existing_sccr_sum": c.existing_sccr_sum,
                            "circuit.facility_short_circuit_contribution_hv_a": c.facility_short_circuit_contribution_hv_a,
                            "circuit.utility_short_circuit_contribution_hv_a": c.utility_short_circuit_contribution_hv_a},
                    formula="existing_sccr_sum + facility_sc_hv_a / utility_sc_hv_a <= 0.1",
                    computed=total, threshold=rb.F_SCCR_MAX.value,
                    reason=f"SCCR sum {_fmt(total)} {'within' if ok else 'exceeds'} 0.1")


def screen_f1(x: ScreenInputs) -> ScreenResult:
    f, c = x.facility, x.circuit
    cites = (rb.F1_PU_MAX.citation, rb.QUICK_REVIEW_A_TO_H)
    if r := _missing("F1", cites, "per-unit contribution unknown", facility__short_circuit_pu=f.short_circuit_pu):
        return r
    if f.short_circuit_pu <= rb.F1_PU_MAX.value:
        return _decided("F1", True, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW,
                        inputs={"facility.short_circuit_pu": f.short_circuit_pu},
                        formula="short_circuit_pu <= 1.2", computed=f.short_circuit_pu, threshold=rb.F1_PU_MAX.value,
                        reason=f"per-unit contribution {_fmt(f.short_circuit_pu)} is 1.2 or less")
    if r := _missing("F1", cites, "per-unit contribution above 1.2 and ICA comparison cannot be made",
                     facility__short_circuit_pu=f.short_circuit_pu, facility__gross_rating_kw=f.gross_rating_kw,
                     circuit__protection_ica_kw=c.protection_ica_kw):
        return r
    lhs = f.gross_rating_kw * f.short_circuit_pu
    rhs = c.protection_ica_kw * rb.F1_ICA_MULTIPLIER.value
    ok = lhs < rhs
    return _decided("F1", ok, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW,
                    inputs={"facility.short_circuit_pu": f.short_circuit_pu,
                            "facility.gross_rating_kw": f.gross_rating_kw,
                            "circuit.protection_ica_kw": c.protection_ica_kw},
                    formula="short_circuit_pu <= 1.2 or gross_rating_kw * short_circuit_pu < protection_ica_kw * 1.2",
                    computed=lhs, threshold=rhs,
                    reason=f"{_fmt(lhs)} {'<' if ok else '>='} {_fmt(rhs)} (protection ICA × 1.2)")


def screen_g(x: ScreenInputs) -> ScreenResult:
    if r := _not_applicable_by_size("G", rb.G_NOT_APPLICABLE_KVA, x):
        return r
    c = x.circuit
    cites = (rb.G_INTERRUPTING_MAX.citation, rb.G_NOT_APPLICABLE_KVA.citation, rb.QUICK_REVIEW_A_TO_H)
    if r := _missing("G", cites, "interrupting duty cannot be computed",
                     circuit__protective_devices=c.protective_devices,
                     circuit__facility_fault_contribution_a=c.facility_fault_contribution_a):
        return r
    if not c.protective_devices:
        return ScreenResult("G", Status.INCONCLUSIVE, cites, blocker=Blocker.UTILITY, missing_inputs=("circuit.protective_devices",),
                            reason="no protective devices listed for the circuit")
    ratios = [((d.existing_fault_duty_a + c.facility_fault_contribution_a) / d.interrupting_rating_a, d.name)
              for d in c.protective_devices]
    worst, worst_name = max(ratios)
    ok = worst <= rb.G_INTERRUPTING_MAX.value
    return _decided("G", ok, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW,
                    inputs={"circuit.facility_fault_contribution_a": c.facility_fault_contribution_a,
                            **{f"circuit.protective_devices[{d.name}]":
                               f"duty={_fmt(d.existing_fault_duty_a)} rating={_fmt(d.interrupting_rating_a)}"
                               for d in c.protective_devices}},
                    formula="max over devices of (existing_fault_duty_a + facility_fault_contribution_a) "
                            "/ interrupting_rating_a <= 0.875",
                    computed=worst, threshold=rb.G_INTERRUPTING_MAX.value,
                    reason=f"worst device {worst_name} at {_fmt(worst)} of interrupting capability")


def screen_h(x: ScreenInputs) -> ScreenResult:
    if r := _not_applicable_by_size("H", rb.H_NOT_APPLICABLE_KVA, x):
        return r
    f, c = x.facility, x.circuit
    cites = (rb.H_TABLE, rb.H_FOUR_WIRE_MAX_FRACTION.citation, rb.QUICK_REVIEW_A_TO_H)
    if r := _missing("H", cites, "line configuration unknown", circuit__primary_line_type=c.primary_line_type,
                     circuit__interconnection_type=c.interconnection_type):
        return r
    base = {"circuit.primary_line_type": c.primary_line_type, "circuit.interconnection_type": c.interconnection_type}
    if c.primary_line_type is PrimaryLineType.THREE_PHASE_THREE_WIRE:
        return _decided("H", True, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW, inputs=base,
                        formula="Table G-1: three-phase three-wire, any interconnection type",
                        computed=None, threshold=None, reason="three-phase three-wire line: pass")
    if (c.primary_line_type is PrimaryLineType.THREE_PHASE_FOUR_WIRE
            and c.interconnection_type is InterconnectionType.SINGLE_PHASE_LINE_TO_NEUTRAL):
        return _decided("H", True, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW, inputs=base,
                        formula="Table G-1: three-phase four-wire, single-phase line-to-neutral",
                        computed=None, threshold=None, reason="single-phase line-to-neutral on four-wire line: pass")
    if r := _missing("H", cites, "10% line-section test cannot be computed",
                     facility__gross_rating_kw=f.gross_rating_kw,
                     circuit__existing_gen_on_line_section_kw=c.existing_gen_on_line_section_kw,
                     circuit__line_section_peak_load_kw=c.line_section_peak_load_kw):
        return r
    aggregate = f.gross_rating_kw + c.existing_gen_on_line_section_kw
    limit = rb.H_FOUR_WIRE_MAX_FRACTION.value * c.line_section_peak_load_kw
    ok = aggregate <= limit
    return _decided("H", ok, cites, fail_as=Classification.MITIGABLE_IN_INITIAL_REVIEW,
                    inputs={**base, "facility.gross_rating_kw": f.gross_rating_kw,
                            "circuit.existing_gen_on_line_section_kw": c.existing_gen_on_line_section_kw,
                            "circuit.line_section_peak_load_kw": c.line_section_peak_load_kw},
                    formula="gross_rating_kw + existing_gen_on_line_section_kw <= 0.10 * line_section_peak_load_kw",
                    computed=aggregate, threshold=limit,
                    reason=f"aggregate {_fmt(aggregate)} kW {'within' if ok else 'exceeds'} {_fmt(limit)} kW")


# --- Screen I (routing, with option checks) -------------------------------------

@dataclass(frozen=True)
class _Route:
    result: ScreenResult
    continue_to_j: bool | None  # None: cannot route


NON_EXPORT_OPTIONS = frozenset({1, 2, 3, 4, 7, 8})
LIMITED_EXPORT_OPTIONS = frozenset({5, 6, 9, 10, 11})


def screen_i(x: ScreenInputs) -> _Route:
    f, c = x.facility, x.circuit
    if f.exports is None:
        return _Route(_missing("I", (rb.I_EXPORT_ROUTE, rb.I_NON_EXPORT_ROUTE), "export intent unknown",  # type: ignore[arg-type]
                               facility__exports=None), None)
    if f.exports:
        if f.export_option is None:
            return _Route(ScreenResult("I", Status.PASS, (rb.I_EXPORT_ROUTE,), inputs={"facility.exports": "True"},
                                       formula="exports == true", reason="exporting facility: continue to Screen J"),
                          True)
        if f.export_option in LIMITED_EXPORT_OPTIONS:
            return _Route(ScreenResult("I", Status.INCONCLUSIVE, (rb.I_EXPORT_ROUTE,), blocker=Blocker.UTILITY,
                                       inputs={"facility.exports": "True", "facility.export_option": str(f.export_option)},
                                       reason=f"Option {f.export_option} (inadvertent/limited export, §M/§Mm) "
                                              "is outside Greenlight's scope"), None)
        return _Route(ScreenResult("I", Status.INCONCLUSIVE, (rb.I_EXPORT_ROUTE,), blocker=Blocker.APPLICANT,
                                   inputs={"facility.exports": "True", "facility.export_option": str(f.export_option)},
                                   reason=f"Option {f.export_option} is a non-export option but the application "
                                          "says the facility exports"), None)

    cites = (rb.I_NON_EXPORT_ROUTE,)
    if f.export_option not in NON_EXPORT_OPTIONS:
        return _Route(ScreenResult("I", Status.INCONCLUSIVE, cites, blocker=Blocker.APPLICANT,
                                   inputs={"facility.exports": "False", "facility.export_option": _fmt(f.export_option)},
                                   missing_inputs=() if f.export_option is not None else ("facility.export_option",),
                                   reason="non-export facility must select Option 1, 2, 3, 4, 7 or 8"), None)
    if f.export_option == 8:
        return _Route(ScreenResult("I", Status.INCONCLUSIVE, cites, blocker=Blocker.UTILITY,
                                   inputs={"facility.exports": "False", "facility.export_option": "8"},
                                   reason="Option 8 screen application (§Mm1) is outside Greenlight's scope"), None)
    if f.export_option == 3:
        return _option_3(x)
    if f.export_option == 4:
        return _option_4(x)
    return _Route(ScreenResult("I", Status.PASS, cites,
                               inputs={"facility.exports": "False", "facility.export_option": str(f.export_option)},
                               formula="non-export Option in {1, 2, 7}",
                               reason=f"non-export via Option {f.export_option}: Screens J–M skipped"), False)


def _option_3(x: ScreenInputs) -> _Route:
    f, c = x.facility, x.circuit
    cites = (rb.I_NON_EXPORT_ROUTE, rb.I_OPTION_3_SERVICE_AMPS.citation, rb.I_OPTION_3_TRANSFORMER.citation,
             rb.I_OPTION_3_NON_ISLANDING)
    if r := _missing("I", cites, "Option 3 conditions cannot be evaluated",
                     facility__gross_rating_kva=f.gross_rating_kva,
                     facility__service_equipment_amps=f.service_equipment_amps,
                     facility__service_voltage_v=f.service_voltage_v, facility__service_phases=f.service_phases,
                     facility__certified_non_islanding=f.certified_non_islanding,
                     circuit__customer_primary_service=c.customer_primary_service):
        return _Route(r, None)
    if f.service_phases not in (1, 3):
        return _Route(ScreenResult("I", Status.INCONCLUSIVE, cites, blocker=Blocker.APPLICANT,
                                   inputs={"facility.service_phases": _fmt(f.service_phases)},
                                   reason="service phase count must be 1 or 3"), None)
    phase_factor = Decimal(1) if f.service_phases == 1 else SQRT3
    service_kva = f.service_voltage_v * f.service_equipment_amps * phase_factor / 1000
    limit_a = rb.I_OPTION_3_SERVICE_AMPS.value * service_kva
    failures = []
    if f.gross_rating_kva > limit_a:
        failures.append(f"(a) {_fmt(f.gross_rating_kva)} kVA exceeds 25% of service equipment ({_fmt(limit_a)} kVA)")
    inputs = {"facility.exports": "False", "facility.export_option": "3",
              "facility.gross_rating_kva": _fmt(f.gross_rating_kva),
              "facility.service_equipment_amps": _fmt(f.service_equipment_amps),
              "facility.service_voltage_v": _fmt(f.service_voltage_v), "facility.service_phases": str(f.service_phases),
              "facility.certified_non_islanding": str(f.certified_non_islanding),
              "circuit.customer_primary_service": str(c.customer_primary_service)}
    if not c.customer_primary_service:
        if c.service_transformer_kva is None:
            return _Route(_missing("I", cites, "Option 3 condition (b) cannot be evaluated",  # type: ignore[arg-type]
                                   circuit__service_transformer_kva=None), None)
        limit_b = rb.I_OPTION_3_TRANSFORMER.value * c.service_transformer_kva
        inputs["circuit.service_transformer_kva"] = _fmt(c.service_transformer_kva)
        if f.gross_rating_kva > limit_b:
            failures.append(f"(b) {_fmt(f.gross_rating_kva)} kVA exceeds 50% of service transformer ({_fmt(limit_b)} kVA)")
    if not f.certified_non_islanding:
        failures.append("(c) facility is not certified non-islanding")
    if failures:
        # An unmet non-export option is an invalid request, not an engineering failure: the applicant
        # must choose another option or apply as exporting.
        return _Route(ScreenResult("I", Status.INCONCLUSIVE, cites, inputs=inputs, blocker=Blocker.APPLICANT,
                                   formula="(a) gross_kva <= 0.25 * service_kva; (b) gross_kva <= 0.50 * transformer_kva; "
                                           "(c) certified_non_islanding",
                                   reason="Option 3 conditions not met: " + "; ".join(failures)), None)
    return _Route(ScreenResult("I", Status.PASS, cites, inputs=inputs,
                               formula="(a) gross_kva <= 0.25 * service_kva; (b) gross_kva <= 0.50 * transformer_kva; "
                                       "(c) certified_non_islanding",
                               reason="non-export via Option 3, all conditions met: Screens J–M skipped"), False)


def _option_4(x: ScreenInputs) -> _Route:
    f = x.facility
    cites = (rb.I_NON_EXPORT_ROUTE, rb.I_OPTION_4_HOST_LOAD.citation)
    if r := _missing("I", cites, "Option 4 condition cannot be evaluated", facility__gross_rating_kw=f.gross_rating_kw,
                     facility__min_host_load_kw_12mo=f.min_host_load_kw_12mo):
        return _Route(r, None)
    limit = rb.I_OPTION_4_HOST_LOAD.value * f.min_host_load_kw_12mo
    inputs = {"facility.exports": "False", "facility.export_option": "4",
              "facility.gross_rating_kw": _fmt(f.gross_rating_kw),
              "facility.min_host_load_kw_12mo": _fmt(f.min_host_load_kw_12mo)}
    if f.gross_rating_kw > limit:
        return _Route(ScreenResult("I", Status.INCONCLUSIVE, cites, inputs=inputs, blocker=Blocker.APPLICANT,
                                   formula="gross_rating_kw <= 0.50 * min_host_load_kw_12mo",
                                   computed=f.gross_rating_kw, threshold=limit,
                                   reason=f"Option 4 condition not met: {_fmt(f.gross_rating_kw)} kW exceeds 50% of "
                                          f"minimum host load ({_fmt(limit)} kW)"), None)
    return _Route(ScreenResult("I", Status.PASS, cites, inputs=inputs,
                               formula="gross_rating_kw <= 0.50 * min_host_load_kw_12mo",
                               computed=f.gross_rating_kw, threshold=limit,
                               reason="non-export via Option 4, condition met: Screens J–M skipped"), False)


# --- Screens J–M ----------------------------------------------------------------

def screen_j(x: ScreenInputs) -> ScreenResult:
    kva = x.facility.gross_rating_kva
    cites = (rb.J_MAX_KVA.citation, rb.J_PASS_ROUTE)
    if r := _missing("J", cites, "gross rating unknown", facility__gross_rating_kva=kva):
        return r
    ok = kva <= rb.J_MAX_KVA.value
    return _decided("J", ok, cites, fail_as=Classification.ROUTING, inputs={"facility.gross_rating_kva": kva},
                    formula="gross_rating_kva <= 30", computed=kva, threshold=rb.J_MAX_KVA.value,
                    reason="30 kVA or less: skip K, L, M" if ok else "above 30 kVA: continue to Screen K")


def screen_k(x: ScreenInputs) -> ScreenResult:
    f = x.facility
    cites = (rb.K_MAX_KW.citation, rb.K_PASS_ROUTE)
    if r := _missing("K", cites, "program or nameplate unknown", facility__program=f.program,
                     facility__gross_rating_kw=f.gross_rating_kw):
        return r
    eligible = f.program in (Program.NEM_1, Program.NEM_2, Program.NBT_1)
    ok = eligible and f.gross_rating_kw <= rb.K_MAX_KW.value
    return _decided("K", ok, cites, fail_as=Classification.ROUTING,
                    inputs={"facility.program": f.program, "facility.gross_rating_kw": f.gross_rating_kw},
                    formula="program in {NEM-1, NEM-2, NBT-1} and gross_rating_kw <= 500",
                    computed=f.gross_rating_kw, threshold=rb.K_MAX_KW.value,
                    reason="NEM/NBT at 500 kW or less: skip L" if ok else "continue to Screen L")


def screen_l(x: ScreenInputs) -> ScreenResult:
    c = x.circuit
    cites = (rb.L_QUESTION, rb.L_FAIL)
    flags = {"circuit.known_stability_limitation": c.known_stability_limitation,
             "circuit.transmission_interdependency": c.transmission_interdependency,
             "circuit.islanding_possible": c.islanding_possible,
             "circuit.ground_fault_overvoltage_possible": c.ground_fault_overvoltage_possible}
    raised = [k for k, v in flags.items() if v]
    unknown = tuple(k for k, v in flags.items() if v is None)
    if not raised and unknown:
        return ScreenResult("L", Status.INCONCLUSIVE, cites, blocker=Blocker.UTILITY, missing_inputs=unknown,
                            inputs={k: str(v) for k, v in flags.items() if v is not None},
                            reason=f"transmission conditions unknown: missing {', '.join(unknown)}")
    return _decided("L", not raised, cites, fail_as=Classification.SUPPLEMENTAL_REQUIRED, inputs=flags,
                    formula="none of (i) stability, (ii) interdependency, (iii) islanding, (iv) overvoltage",
                    computed=None, threshold=None,
                    reason="no transmission conditions" if not raised else "raised: " + ", ".join(raised))


def screen_m(x: ScreenInputs) -> ScreenResult:
    f, c = x.facility, x.circuit
    if c.ica_sg_min_kw is not None and c.ica_of_min_kw is not None:
        cites = (rb.M_ICA_FRACTION.citation, rb.M_ICA_OF, rb.M_BOTH_REQUIRED, rb.M_FAIL)
        if r := _missing("M", cites, "gross nameplate unknown", facility__gross_rating_kw=f.gross_rating_kw):
            return r
        limit = rb.M_ICA_FRACTION.value * min(c.ica_sg_min_kw, c.ica_of_min_kw)
        ok = f.gross_rating_kw <= limit
        return _decided("M", ok, cites, fail_as=Classification.SUPPLEMENTAL_REQUIRED,
                        inputs={"facility.gross_rating_kw": f.gross_rating_kw,
                                "circuit.ica_sg_min_kw": c.ica_sg_min_kw, "circuit.ica_of_min_kw": c.ica_of_min_kw},
                        formula="gross_rating_kw <= 0.90 * ica_sg_min_kw and gross_rating_kw <= 0.90 * ica_of_min_kw",
                        computed=f.gross_rating_kw, threshold=limit,
                        reason=f"{_fmt(f.gross_rating_kw)} kW {'within' if ok else 'exceeds'} 90% of ICA ({_fmt(limit)} kW)")
    if (c.ica_sg_min_kw is None) != (c.ica_of_min_kw is None):
        return _missing("M", (rb.M_ICA_FRACTION.citation, rb.M_ICA_OF), "only one ICA value present",  # type: ignore[return-value]
                        circuit__ica_sg_min_kw=c.ica_sg_min_kw, circuit__ica_of_min_kw=c.ica_of_min_kw)
    cites = (rb.M_FALLBACK_FRACTION.citation,)
    if r := _missing("M", cites, "no ICA values; line-section penetration cannot be computed",
                     facility__gross_rating_kw=f.gross_rating_kw,
                     circuit__existing_gen_on_line_section_kw=c.existing_gen_on_line_section_kw,
                     circuit__line_section_peak_load_kw=c.line_section_peak_load_kw):
        return r
    aggregate = f.gross_rating_kw + c.existing_gen_on_line_section_kw
    limit = rb.M_FALLBACK_FRACTION.value * c.line_section_peak_load_kw
    ok = aggregate < limit
    return _decided("M", ok, cites, fail_as=Classification.SUPPLEMENTAL_REQUIRED,
                    inputs={"facility.gross_rating_kw": f.gross_rating_kw,
                            "circuit.existing_gen_on_line_section_kw": c.existing_gen_on_line_section_kw,
                            "circuit.line_section_peak_load_kw": c.line_section_peak_load_kw},
                    formula="gross_rating_kw + existing_gen_on_line_section_kw < 0.15 * line_section_peak_load_kw",
                    computed=aggregate, threshold=limit,
                    reason=f"no ICA values; aggregate {_fmt(aggregate)} kW "
                           f"{'below' if ok else 'not below'} 15% of peak ({_fmt(limit)} kW)")


# --- flow -----------------------------------------------------------------------

def _skipped(screen: str, by: str, citation: rb.Citation, reason: str) -> ScreenResult:
    return ScreenResult(screen, Status.SKIPPED, (citation,), routed_by=by, reason=reason)


def _unroutable(screen: str, by: ScreenResult) -> ScreenResult:
    return ScreenResult(screen, Status.INCONCLUSIVE, by.citations, blocker=by.blocker, routed_by=by.screen,
                        reason=f"depends on Screen {by.screen}, which is inconclusive")


def _with_synthetic(result: ScreenResult, synthetic: frozenset[str]) -> ScreenResult:
    used = tuple(sorted(k for k in result.inputs if k.startswith("circuit.") and k.removeprefix("circuit.") in synthetic))
    return replace(result, synthetic_inputs=used) if used else result


@dataclass(frozen=True)
class InitialReview:
    results: tuple[ScreenResult, ...]
    input_hash: str
    engine_version: str = rb.ENGINE_VERSION

    def by_screen(self) -> dict[str, ScreenResult]:
        return {r.screen: r for r in self.results}

    def disposition_floor(self) -> Disposition:
        """The least severe disposition the evidence allows. The agent may propose worse, never better."""
        counted = [r for r in self.results if r.classification is not Classification.ROUTING]
        if any(r.status is Status.INCONCLUSIVE and r.blocker is Blocker.APPLICANT for r in counted):
            return Disposition.DEFICIENCY_NOTICE
        if any(r.status is Status.FAIL for r in counted):
            return Disposition.SUPPLEMENTAL_REVIEW_REQUIRED
        if any(r.status is Status.INCONCLUSIVE for r in counted):
            return Disposition.NEEDS_ENGINEER_DETERMINATION
        return Disposition.INITIAL_REVIEW_PASS


def input_hash(x: ScreenInputs) -> str:
    payload = json.dumps(asdict(x), sort_keys=True, default=_fmt, separators=(",", ":"))
    return hashlib.sha256(f"{rb.ENGINE_VERSION}|{payload}".encode()).hexdigest()


ALWAYS_RUN: tuple[Callable[[ScreenInputs], ScreenResult], ...] = (
    screen_a, screen_b, screen_c, screen_d, screen_e, screen_f, screen_f1, screen_g, screen_h,
)


def run_initial_review(x: ScreenInputs) -> InitialReview:
    """Screens A–H always run (every failure is reported at once); I routes J–M."""
    results = [fn(x) for fn in ALWAYS_RUN]

    route = screen_i(x)
    results.append(route.result)
    if route.continue_to_j is None:
        results += [_unroutable(s, route.result) for s in ("J", "K", "L", "M")]
    elif route.continue_to_j is False:
        results += [_skipped(s, "I", rb.I_NON_EXPORT_ROUTE, "non-export facility") for s in ("J", "K", "L", "M")]
    else:
        j = screen_j(x)
        results.append(j)
        if j.status is Status.INCONCLUSIVE:
            results += [_unroutable(s, j) for s in ("K", "L", "M")]
        elif j.status is Status.PASS:
            results += [_skipped(s, "J", rb.J_PASS_ROUTE, "30 kVA or less") for s in ("K", "L", "M")]
        else:
            k = screen_k(x)
            results.append(k)
            if k.status is Status.INCONCLUSIVE:
                results.append(_unroutable("L", k))
            elif k.status is Status.PASS:
                results.append(_skipped("L", "K", rb.K_PASS_ROUTE, "NEM/NBT at 500 kW or less"))
            else:
                results.append(screen_l(x))
            results.append(screen_m(x))

    synthetic = x.circuit.synthetic_fields
    return InitialReview(tuple(_with_synthetic(r, synthetic) for r in results), input_hash(x))
