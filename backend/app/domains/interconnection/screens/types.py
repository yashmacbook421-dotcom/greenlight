"""Inputs and outputs of the screen engine. Plain frozen dataclasses, Decimal arithmetic.

Every input is optional. A missing value never defaults to something
convenient: the screen that needs it returns INCONCLUSIVE and names it.
"""

import enum
from dataclasses import dataclass, field
from decimal import Decimal

from app.domains.interconnection.screens.rulebook import Citation


class Status(enum.StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INCONCLUSIVE = "INCONCLUSIVE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    SKIPPED = "SKIPPED"


class Blocker(enum.StrEnum):
    APPLICANT = "applicant"  # the packet must supply it → deficiency item
    UTILITY = "utility"  # circuit data or utility practice → engineer


class Classification(enum.StrEnum):
    MITIGABLE_IN_INITIAL_REVIEW = "mitigable_in_initial_review"  # §G.1, Screens B–H
    SUPPLEMENTAL_REQUIRED = "supplemental_required"  # Screens A, L, M
    ROUTING = "routing"  # J and K "fail" only means "continue to the next screen"


class Program(enum.StrEnum):
    NEM_1 = "NEM-1"
    NEM_2 = "NEM-2"
    NBT_1 = "NBT-1"
    OTHER = "other"


class PrimaryLineType(enum.StrEnum):
    THREE_PHASE_THREE_WIRE = "three_phase_three_wire"
    THREE_PHASE_FOUR_WIRE = "three_phase_four_wire"
    MIXED = "mixed"


class InterconnectionType(enum.StrEnum):
    SINGLE_PHASE_LINE_TO_NEUTRAL = "single_phase_line_to_neutral"
    OTHER = "other"


@dataclass(frozen=True)
class Facility:
    """What the applicant's packet establishes (after extraction and reconciliation)."""

    gross_rating_kva: Decimal | None = None
    gross_rating_kw: Decimal | None = None
    inverter_based: bool | None = None
    starts_by_motoring: bool | None = None
    equipment_certified: bool | None = None
    certified_non_islanding: bool | None = None
    single_phase: bool | None = None
    on_240v_center_tap: bool | None = None
    phase_imbalance_kva: Decimal | None = None
    exports: bool | None = None
    # Screen I option number. None with exports=True means ordinary full export.
    export_option: int | None = None
    program: Program | None = None
    short_circuit_pu: Decimal | None = None
    service_equipment_amps: Decimal | None = None
    service_voltage_v: Decimal | None = None
    service_phases: int | None = None
    min_host_load_kw_12mo: Decimal | None = None


@dataclass(frozen=True)
class ProtectiveDevice:
    name: str
    interrupting_rating_a: Decimal
    existing_fault_duty_a: Decimal


@dataclass(frozen=True)
class Circuit:
    """What the utility knows about the point of interconnection."""

    networked_secondary: bool | None = None
    spot_network: bool | None = None
    spot_network_max_load_kw: Decimal | None = None
    existing_inverter_gen_on_spot_network_kw: Decimal | None = None
    customer_primary_service: bool | None = None
    service_transformer_kva: Decimal | None = None
    existing_gross_on_service_transformer_kva: Decimal | None = None
    secondary_conductor_rating_kva: Decimal | None = None
    existing_sccr_sum: Decimal | None = None
    facility_short_circuit_contribution_hv_a: Decimal | None = None
    utility_short_circuit_contribution_hv_a: Decimal | None = None
    protection_ica_kw: Decimal | None = None
    protective_devices: tuple[ProtectiveDevice, ...] | None = None
    facility_fault_contribution_a: Decimal | None = None
    primary_line_type: PrimaryLineType | None = None
    interconnection_type: InterconnectionType | None = None
    line_section_peak_load_kw: Decimal | None = None
    existing_gen_on_line_section_kw: Decimal | None = None
    known_stability_limitation: bool | None = None
    transmission_interdependency: bool | None = None
    islanding_possible: bool | None = None
    ground_fault_overvoltage_possible: bool | None = None
    ica_sg_min_kw: Decimal | None = None
    ica_of_min_kw: Decimal | None = None
    synthetic_fields: frozenset[str] = frozenset()


@dataclass(frozen=True)
class UtilityPractice:
    """Values the tariff delegates to 'established Distribution Provider practice'."""

    source: str
    d_transformer_rating_multiplier: Decimal | None = None
    e_max_phase_imbalance_kva: Decimal | None = None


@dataclass(frozen=True)
class ScreenInputs:
    facility: Facility
    circuit: Circuit
    practice: UtilityPractice | None = None


@dataclass(frozen=True)
class ScreenResult:
    screen: str
    status: Status
    citations: tuple[Citation, ...]
    inputs: dict[str, str] = field(default_factory=dict)
    formula: str | None = None
    computed: Decimal | None = None
    threshold: Decimal | None = None
    classification: Classification | None = None
    reason: str | None = None
    missing_inputs: tuple[str, ...] = ()
    blocker: Blocker | None = None
    routed_by: str | None = None
    synthetic_inputs: tuple[str, ...] = ()
