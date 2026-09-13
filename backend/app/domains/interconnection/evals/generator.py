"""Synthetic interconnection packets with injected defects: the eval's ground truth.

Real application packets contain customer PII and are not public, so packets are generated.
Equipment is drawn from real rows of the pinned CEC inverter list (actual manufacturers,
models and listed output power); electrical values are derived from them. Circuits are
synthetic and labelled so. Every labelled line written into a PDF is also recorded as an
oracle fact (field, value and unit as written, page, exact quote), so extraction can be
scored and the downstream pipeline can be evaluated in isolation.

The expected disposition for each defect family is stated here, from what the defect means
under Rule 21, not computed by the engine under test.
"""

import io
import random
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.equipment.lookup import ListedInverter, _index
from app.domains.interconnection.screens.types import (
    Circuit,
    InterconnectionType,
    PrimaryLineType,
    ProtectiveDevice,
)

D = Disposition


@dataclass(frozen=True)
class Family:
    name: str
    profile: str  # residential | commercial
    expected: Disposition
    detections: tuple[dict[str, str], ...]  # what a correct review must surface
    description: str
    # Signals the defect logically entails beyond its core detection (e.g. a missing spec sheet also leaves the
    # fault current unknown). Allowed, reported separately, and not counted as false positives.
    consequences: tuple[dict[str, str], ...] = ()


FAMILIES: dict[str, Family] = {f.name: f for f in [
    Family("clean_residential", "residential", D.INITIAL_REVIEW_PASS, (), "Complete, consistent rooftop packet"),
    Family("clean_commercial", "commercial", D.INITIAL_REVIEW_PASS, (), "Complete, consistent commercial packet"),
    Family("nameplate_rounding", "residential", D.INITIAL_REVIEW_PASS, (),
           "Form rounds the system rating (e.g. 7.6 kW vs 7,616 W on the spec sheet): not a defect"),
    Family("quantity_conflict", "residential", D.DEFICIENCY_NOTICE,
           ({"kind": "discrepancy", "ref": "gross_rating_kw"},), "One-line diagram shows 2 inverters, form shows 1",
           consequences=({"kind": "discrepancy", "ref": "gross_rating_kva"},)),
    Family("crosses_30_kva", "residential", D.DEFICIENCY_NOTICE,
           ({"kind": "discrepancy", "ref": "gross_rating_kva"},),
           "Form states 29.9 kVA; spec sheet × quantity is just over 30 kVA (Screen J threshold)"),
    Family("missing_spec_sheet", "residential", D.DEFICIENCY_NOTICE,
           ({"kind": "missing_document", "ref": "inverter_spec_sheet"},), "No inverter specification sheet",
           consequences=({"kind": "screen", "ref": "E", "status": "INCONCLUSIVE"},   # phase configuration unknown
                         {"kind": "screen", "ref": "F1", "status": "INCONCLUSIVE"})),  # fault current unknown
    Family("uncertified_inverter", "residential", D.SUPPLEMENTAL_REVIEW_REQUIRED,
           ({"kind": "screen", "ref": "B", "status": "FAIL"},), "Inverter model is not on the certified list"),
    Family("transformer_overload", "residential", D.SUPPLEMENTAL_REVIEW_REQUIRED,
           ({"kind": "screen", "ref": "D", "status": "FAIL"},), "Service transformer too small for existing + new DER"),
    Family("invalid_non_export_option", "residential", D.DEFICIENCY_NOTICE,
           ({"kind": "screen", "ref": "I", "status": "INCONCLUSIVE"},),
           "Claims non-export Option 3 but exceeds 25% of the service rating"),
    Family("applicant_conflict", "residential", D.DEFICIENCY_NOTICE,
           ({"kind": "discrepancy", "ref": "applicant_name"},), "One-line diagram names a different applicant"),
    Family("missing_fault_current", "residential", D.DEFICIENCY_NOTICE,
           ({"kind": "screen", "ref": "F1", "status": "INCONCLUSIVE"},), "Spec sheet omits the output fault current"),
    Family("ica_exceeded", "commercial", D.SUPPLEMENTAL_REVIEW_REQUIRED,
           ({"kind": "screen", "ref": "M", "status": "FAIL"},), "System exceeds 90% of the line section's ICA"),
    Family("illegible_scan", "residential", D.INITIAL_REVIEW_PASS, (),
           "Application form submitted as a scanned image (no text layer)"),
]}

FIRST = ["Jordan", "Priya", "Luis", "Mei", "Samuel", "Aisha", "Grace", "Omar", "Hana", "Diego", "Ruth", "Kenji"]
LAST = ["Rivera", "Patel", "Nguyen", "Okafor", "Chen", "Silva", "Kowalski", "Haddad", "Tanaka", "Moreno"]
STREETS = ["Oak St", "Mission Ave", "Laurel Dr", "Sequoia Way", "Harbor Blvd", "Vista Ct", "Canyon Rd"]
CITIES = ["Fresno", "San Jose", "Santa Rosa", "Bakersfield", "Oakland", "Chico", "Salinas"]
INSTALLERS = ["Golden State Solar", "Bayline Energy", "Sierra Sun Installers", "Coastal Power Co"]


@dataclass(frozen=True)
class OracleFact:
    document_kind: str
    field: str
    value_as_written: str
    unit_as_written: str | None
    page: int
    quote: str
    instance: str | None = None


@dataclass
class GeneratedDocument:
    kind: str
    filename: str
    data: bytes


@dataclass
class Packet:
    packet_id: str
    family: Family
    applicant_name: str
    site_address: str
    installer_name: str
    documents: list[GeneratedDocument]
    facts: list[OracleFact]
    circuit: Circuit
    synthetic_fields: list[str]
    identity_conflicts: list[str] = field(default_factory=list)

    def ground_truth(self) -> dict[str, Any]:
        return {"packet_id": self.packet_id, "family": self.family.name, "profile": self.family.profile,
                "expected_disposition": self.family.expected.value, "detections": list(self.family.detections),
                "consequences": list(self.family.consequences),
                "documents": [d.kind for d in self.documents], "facts": [vars(f) for f in self.facts]}


# --- rendering ------------------------------------------------------------------------------------------


class _Doc:
    """Collects labelled lines per page, renders them, and records each labelled line as an oracle fact."""

    def __init__(self, kind: str, title: str) -> None:
        self.kind, self.title = kind, title
        self.pages: list[list[str]] = [[title, ""]]
        self.facts: list[OracleFact] = []

    def line(self, text: str) -> None:
        self.pages[-1].append(text)

    def fact(self, label: str, field_name: str, value: str, unit: str | None = None, *, instance: str | None = None) -> None:
        text = f"{label}: {value}" + (f" {unit}" if unit else "")
        self.pages[-1].append(text)
        self.facts.append(OracleFact(self.kind, field_name, value, unit, len(self.pages), text, instance))

    def statement(self, text: str, field_name: str, value: str, unit: str | None = None) -> None:
        """An unlabelled line that still states a fact (e.g. a diagram annotation)."""
        self.pages[-1].append(text)
        self.facts.append(OracleFact(self.kind, field_name, value, unit, len(self.pages), text))

    def choice(self, label: str, field_name: str, choice: str, shown: str) -> None:
        text = f"{label}: {shown}"
        self.pages[-1].append(text)
        self.facts.append(OracleFact(self.kind, field_name, choice, None, len(self.pages), text))

    def new_page(self) -> None:
        self.pages.append([f"{self.title} (continued)", ""])

    def pdf(self, scanned: bool = False) -> bytes:
        pdf = FPDF(format="letter")
        pdf.set_auto_page_break(False)
        for lines in self.pages:
            pdf.add_page()
            if scanned:
                img = Image.new("L", (1275, 1650), 250)
                draw = ImageDraw.Draw(img)
                font = ImageFont.load_default(size=30)
                for i, text in enumerate(lines):
                    draw.text((90, 110 + i * 48), text, fill=25, font=font)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                pdf.image(buf, x=0, y=0, w=pdf.w, h=pdf.h)
            else:
                pdf.set_font("Helvetica", size=11)
                pdf.set_xy(18, 18)
                for i, text in enumerate(lines):
                    pdf.set_font("Helvetica", style="B" if i == 0 else "", size=14 if i == 0 else 11)
                    pdf.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        return bytes(pdf.output())


def _w(kw: Decimal) -> str:
    return f"{int((kw * 1000).quantize(Decimal(1), ROUND_HALF_UP)):,}"


def _d(x: Decimal, places: str = "0.1") -> str:
    return format(x.quantize(Decimal(places), ROUND_HALF_UP).normalize(), "f")


# --- equipment ----------------------------------------------------------------------------------------------


def _pool(profile: str) -> list[ListedInverter]:
    rows = [i for v in _index().values() for i in v if i.list == "solar" and i.max_continuous_output_kw]
    if profile == "residential":
        pool = [i for i in rows if i.nominal_vac == 240 and Decimal(3) <= i.max_continuous_output_kw <= Decimal("7.7")
                and "{" not in i.model and "," not in i.model and len(i.model) <= 30]
    else:
        pool = [i for i in rows if i.nominal_vac == 480 and Decimal(30) <= i.max_continuous_output_kw <= Decimal(125)
                and "," not in i.model and len(i.model) <= 30]
    return sorted(pool, key=lambda i: (i.manufacturer, i.model, i.voltage_option))


# --- packet ---------------------------------------------------------------------------------------------------


def generate(family_name: str, seed: int) -> Packet:
    fam = FAMILIES[family_name]
    rng = random.Random(f"{family_name}:{seed}")
    residential = fam.profile == "residential"
    # Some defects only exist for certain ratings; constrain the draw so each defect holds by construction.
    minimum_kw = {"crosses_30_kva": Decimal("7.51"),  # 4 units must exceed 30 kVA
                  "transformer_overload": Decimal("5.1"),  # 10 kVA existing + unit must exceed a 15 kVA transformer
                  "invalid_non_export_option": Decimal("6.1")}.get(family_name, Decimal(0))  # > 25% of 100 A x 240 V
    pool = [i for i in _pool(fam.profile) if i.max_continuous_output_kw >= minimum_kw]
    if family_name == "nameplate_rounding":  # the rating must visibly change when rounded to 0.1 kW
        pool = [i for i in pool if i.max_continuous_output_kw.quantize(Decimal("0.001"))
                != i.max_continuous_output_kw.quantize(Decimal("0.1"))]
    inv = rng.choice(pool)

    unit_kw = inv.max_continuous_output_kw.quantize(Decimal("0.001"))
    if residential:
        qty = 4 if family_name == "crosses_30_kva" else 1
        voltage, phases, panel_a = Decimal(240), 1, Decimal(100 if family_name == "invalid_non_export_option" else 200)
    else:
        qty = rng.randint(2, 4)
        voltage, phases, panel_a = Decimal(480), 3, Decimal(800)
    phase_factor = Decimal(1) if phases == 1 else Decimal(3).sqrt()
    cont_a = (unit_kw * 1000 / (voltage * phase_factor)).quantize(Decimal("0.1"), ROUND_HALF_UP)
    pu = Decimal(rng.choice(["1.05", "1.08", "1.1", "1.12", "1.15", "1.18"]))
    fault_a = (cont_a * pu).quantize(Decimal("0.1"), ROUND_HALF_UP)
    gross_kw = unit_kw * qty
    model = inv.model + ("-X9" if family_name == "uncertified_inverter" else "")

    applicant = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
    address = f"{rng.randint(100, 9899)} {rng.choice(STREETS)}, {rng.choice(CITIES)}, CA"
    installer = rng.choice(INSTALLERS)
    other_applicant = applicant
    while other_applicant == applicant:
        other_applicant = f"{rng.choice(FIRST)} {rng.choice(LAST)}"

    # Application form
    form = _Doc("application_form", "PG&E Rule 21 Interconnection Request - Generating Facility")
    form.fact("Applicant name", "applicant_name", applicant)
    form.fact("Service address", "site_address", address)
    form.fact("Installer", "installer_name", installer)
    program = "NBT-1"
    form.choice("Tariff", "tariff_program", program, "Net Billing Tariff (NBT-1)")
    if family_name == "invalid_non_export_option":
        form.choice("Export to grid", "export_intent", "non_export", "No - non-export")
        form.fact("Non-export option (Screen I)", "non_export_option", "3")
    else:
        form.choice("Export to grid", "export_intent", "export", "Yes - export")
    form.new_page()
    stated_kw = _d(gross_kw, "0.1") if family_name == "nameplate_rounding" else _d(gross_kw, "0.001")
    form.fact("System AC rating", "system_ac_rating", stated_kw, "kW")
    stated_kva = "29.9" if family_name == "crosses_30_kva" else _d(gross_kw, "0.001")
    form.fact("System apparent power rating", "system_apparent_power_rating", stated_kva, "kVA")
    form.fact("Inverter model", "inverter_model", model)
    form.fact("Number of inverters", "inverter_quantity", str(qty))
    form.fact("Main service panel rating", "service_panel_rating", _d(panel_a, "1"), "A")
    form.fact("Service voltage", "service_voltage", _d(voltage, "1"), "V")
    form.fact("Service phases", "service_phases", str(phases))

    # One-line diagram
    one_line = _Doc("one_line_diagram", "Single Line Diagram")
    one_line.fact("Customer", "applicant_name", other_applicant if family_name == "applicant_conflict" else applicant)
    one_line.statement(f"Utility meter -> Main service panel {_d(panel_a, '1')} A -> AC disconnect -> inverter(s)",
                       "service_panel_rating", _d(panel_a, "1"), "A")
    one_line.fact("Inverter", "inverter_model", model)
    one_line.fact("Inverter quantity", "inverter_quantity", "2" if family_name == "quantity_conflict" else str(qty))
    one_line.line("PV array -> DC disconnect -> inverter DC input")

    # Spec sheet
    spec = _Doc("inverter_spec_sheet", f"{inv.manufacturer} - Inverter Datasheet")
    spec.fact("Manufacturer", "inverter_manufacturer", inv.manufacturer)
    spec.fact("Model", "inverter_model", model)
    spec.fact("Rated AC output power", "inverter_rated_ac_power", _w(unit_kw), "W")
    spec.fact("Maximum apparent power", "inverter_max_apparent_power", _w(unit_kw), "VA")
    spec.fact("Maximum continuous output current", "inverter_max_continuous_output_current", _d(cont_a), "A")
    if family_name != "missing_fault_current":
        spec.fact("Maximum output fault current", "inverter_max_fault_current", _d(fault_a), "A")
    spec.fact("Nominal AC voltage", "inverter_nominal_ac_voltage", _d(voltage, "1"), "V")
    if residential:
        spec.choice("AC connection", "inverter_phase_configuration", "single_phase_240v_split", "240 V split-phase (L1-L2)")
    else:
        spec.choice("AC connection", "inverter_phase_configuration", "three_phase", "3-phase, 4-wire")
    spec.fact("Certification", "inverter_certification", "UL 1741 SB")

    documents = [GeneratedDocument("application_form", "application_form.pdf",
                                   form.pdf(scanned=family_name == "illegible_scan")),
                 GeneratedDocument("one_line_diagram", "single_line_diagram.pdf", one_line.pdf())]
    facts = form.facts + one_line.facts
    if family_name != "missing_spec_sheet":
        documents.append(GeneratedDocument("inverter_spec_sheet", "inverter_datasheet.pdf", spec.pdf()))
        facts += spec.facts

    gross_kva = gross_kw
    if residential:
        transformer = Decimal(15) if family_name == "transformer_overload" else Decimal(50) if gross_kva > 20 else Decimal(25)
        existing = Decimal(10) if family_name == "transformer_overload" else Decimal(rng.randint(0, 5))
        circuit = Circuit(networked_secondary=False, service_transformer_kva=transformer,
                          existing_gross_on_service_transformer_kva=existing, customer_primary_service=False)
    else:
        circuit = Circuit(
            networked_secondary=False, customer_primary_service=False,
            service_transformer_kva=(gross_kva * Decimal("1.5")).quantize(Decimal(1)),
            existing_gross_on_service_transformer_kva=Decimal(0), existing_sccr_sum=Decimal("0.02"),
            facility_short_circuit_contribution_hv_a=Decimal(40), utility_short_circuit_contribution_hv_a=Decimal(6000),
            protective_devices=(ProtectiveDevice("substation-breaker", Decimal(25000), Decimal(14000)),
                                ProtectiveDevice("line-recloser", Decimal(12000), Decimal(6500))),
            facility_fault_contribution_a=Decimal(60), primary_line_type=PrimaryLineType.THREE_PHASE_FOUR_WIRE,
            interconnection_type=InterconnectionType.OTHER, line_section_peak_load_kw=Decimal(9000),
            existing_gen_on_line_section_kw=Decimal(150), known_stability_limitation=False,
            transmission_interdependency=False, islanding_possible=False, ground_fault_overvoltage_possible=False,
            ica_sg_min_kw=(gross_kw * (Decimal("1.05") if family_name == "ica_exceeded" else Decimal("1.6"))).quantize(Decimal(1)),
            ica_of_min_kw=(gross_kw * Decimal(2)).quantize(Decimal(1)), protection_ica_kw=(gross_kw * 3).quantize(Decimal(1)),
        )
    synthetic = sorted(k for k, v in vars(circuit).items() if v is not None and k != "synthetic_fields")
    circuit = replace(circuit, synthetic_fields=frozenset(synthetic))
    return Packet(f"{family_name}-{seed}", fam, applicant, address, installer, documents, facts, circuit, synthetic,
                  identity_conflicts=["applicant_name"] if family_name == "applicant_conflict" else [])


def corpus(per_family: int, seed: int = 0, families: list[str] | None = None) -> list[Packet]:
    names = families or list(FAMILIES)
    return [generate(name, seed + i) for name in names for i in range(per_family)]
