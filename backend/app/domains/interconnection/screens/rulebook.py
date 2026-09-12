"""Every threshold and routing rule the screen engine uses, with its source.

Nothing numeric in the engine is a bare literal: it comes from here, and each
entry carries the section, sheet and a verbatim quote from the pinned tariff.
tests/test_rulebook_citations.py asserts every quote appears on its sheet.

Where the tariff text is ambiguous, `interpretation` records the reading we
implemented, so a reviewer can disagree with it explicitly.
"""

from dataclasses import dataclass
from decimal import Decimal

RULESET = "pge_rule21_2025-08-29"
ENGINE_VERSION = "rule21-initial-review/0.1.0"


@dataclass(frozen=True)
class Citation:
    section: str
    sheet: int
    quote: str
    interpretation: str | None = None

    def as_dict(self) -> dict[str, object]:
        d: dict[str, object] = {"ruleset": RULESET, "section": self.section, "sheet": self.sheet, "quote": self.quote}
        if self.interpretation:
            d["interpretation"] = self.interpretation
        return d


@dataclass(frozen=True)
class Threshold:
    value: Decimal
    citation: Citation


# --- §G.1 framing ---------------------------------------------------------------

INITIAL_REVIEW_SCOPE = Citation(
    "G.1", 140, "The Initial Review consists of Screens A through M.")
QUICK_REVIEW_A_TO_H = Citation(
    "G.1", 140,
    "If any of the Screens A through H are not passed, a quick review of the failed Screen(s) may "
    "determine the requirements to address the failure(s). Otherwise, Supplemental Review is required.")

# --- Screen A -------------------------------------------------------------------

A_QUESTION = Citation("G.1.a", 140, "Screen A: Is the PCC on a Networked Secondary System?")
A_FAIL = Citation("G.1.a", 140, "If Yes (fail), must go to Supplemental Review except if the Generating "
                                "Facility is on a Spot Network and meets the following criteria.")
A_SPOT_INVERTER = Citation("G.1.a", 140, "The proposed Generating Facility must utilize an inverter-based "
                                         "equipment package")
A_SPOT_MAX_FRACTION = Threshold(Decimal("0.05"), Citation(
    "G.1.a", 140, "shall not exceed the smaller of 5 % of a Spot Network's maximum load or 50 kW"))
A_SPOT_MAX_KW = Threshold(Decimal("50"), A_SPOT_MAX_FRACTION.citation)

# --- Screen B -------------------------------------------------------------------

B_QUESTION = Citation("G.1.b", 141, "Does the Interconnection Request propose to use Certified Equipment as "
                                    "set out in Section L or does the equipment have interim Distribution "
                                    "Provider approval?")

# --- Screen C -------------------------------------------------------------------

C_APPLICABILITY = Citation("G.1.c", 142, "This Screen only applies to Generating Facilities that start by "
                                         "motoring the Generator(s).")

# --- Screen D -------------------------------------------------------------------

D_QUESTION = Citation(
    "G.1.d", 143,
    "Do the maximum aggregated Gross Ratings for all the Generating Facilities connected to a secondary "
    "distribution transformer exceed the transformer or secondary conductor rating, modified per "
    "established Distribution Provider practice, absent any Generating Facilities?",
    interpretation="The tariff gives no numeric modifier; it comes from UtilityPractice and is labelled with its source.")

# --- Screen E -------------------------------------------------------------------

E_QUESTION = Citation(
    "G.1.e", 143,
    "If the proposed Generating Facility is single-phase and is to be interconnected on a center tap neutral "
    "of a 240 volt service, does it cause unacceptable imbalance between the two phases of the 240 volt service?",
    interpretation="'Unacceptable' is not quantified in the tariff; the limit comes from UtilityPractice.")

# --- Screens F, F1 --------------------------------------------------------------

F_NOT_APPLICABLE_KVA = Threshold(Decimal("30"), Citation(
    "G.1.f", 144, "This Screen does not apply to Generating Facilities with a Gross Rating of 30 kVA or less."))
F_SCCR_MAX = Threshold(Decimal("0.1"), Citation(
    "G.1.f", 144,
    "the sum of the Short Circuit Contribution Ratios of all Generating Facilities connected to Distribution "
    "Provider's Distribution System circuit that serves the Generating Facility must be less than or equal to 0.1."))
SCCR_DEFINITION = Citation(
    "C", 33,
    "The ratio of the Generating Facility's short circuit contribution to the short circuit contribution "
    "provided through Distribution Provider's Distribution System for a three-phase fault at the high voltage "
    "side of the distribution transformer")
F1_PU_MAX = Threshold(Decimal("1.2"), Citation(
    "G.1.f", 145,
    "Is the short circuit current contribution less than or equal to 1.2 per unit or is the Generating Facility "
    "Gross Nameplate Rating multiplied by its per unit contribution less than the Protection Integrated Capacity "
    "Analysis (ICA) Value multiplied by 1.2 per unit?",
    interpretation="The 30 kVA exclusion note appears under Screen F only; F1 is applied at every size."))
F1_ICA_MULTIPLIER = Threshold(Decimal("1.2"), F1_PU_MAX.citation)

# --- Screen G -------------------------------------------------------------------

G_NOT_APPLICABLE_KVA = Threshold(Decimal("30"), Citation(
    "G.1.g", 146, "This Screen does not apply to Generating Facilities with a Gross Rating of 30 kVA or less."))
G_INTERRUPTING_MAX = Threshold(Decimal("0.875"), Citation(
    "G.1.g", 145,
    "cause any distribution protective devices and equipment (including, but not limited to, substation "
    "breakers, fuse cutouts, and line reclosers), or Interconnection Request equipment on the system to exceed "
    "87.5 % of the short circuit interrupting capability; or is the Interconnection proposed for a circuit that "
    "already exceeds 87.5 % of the short circuit interrupting capability?",
    interpretation="The facility's full fault contribution is added to every device's existing duty (conservative)."))

# --- Screen H -------------------------------------------------------------------

H_NOT_APPLICABLE_KVA = Threshold(Decimal("30"), Citation(
    "G.1.h", 146, "This Screen does not apply to Generating Facilities with a Gross Rating of 30 kVA or less"))
H_TABLE = Citation("G.1.h", 146, "determine from Table G.1 if the proposed Generating Facility passes the Screen.")
H_FOUR_WIRE_MAX_FRACTION = Threshold(Decimal("0.10"), Citation(
    "G.1.h", 146, "or equal to 10% of Line Section peak load",
    interpretation="'Aggregate' is read as existing generation on the line section plus this facility (conservative)."))

# --- Screen I -------------------------------------------------------------------

I_EXPORT_ROUTE = Citation("G.1.i", 147, "If Yes, Continue to Screen J. This includes Options 5, 6, 9, 10, and 11.")
I_NON_EXPORT_ROUTE = Citation(
    "G.1.i", 147,
    "the Generating Facility must incorporate Options 1, 2, 3, 4, 7, or 8 below. Following that selection, "
    "Screen J, K, L, and M are skipped and Initial Review is complete.")
I_OPTION_3_SERVICE_AMPS = Threshold(Decimal("0.25"), Citation(
    "G.1.i", 148,
    "the total Gross Capacity of the Generating Facility must be no more than 25% of the nominal ampere rating "
    "of Producer's service equipment",
    interpretation="Service ampere rating is converted to kVA with the service voltage and phase count."))
I_OPTION_3_TRANSFORMER = Threshold(Decimal("0.50"), Citation(
    "G.1.i", 148,
    "the total Gross Capacity of the Generating Facility must be no more than 50% of Producer's service "
    "transformer capacity rating (this capacity requirement does not apply to Customers taking primary service "
    "without an intervening transformer)"))
I_OPTION_3_NON_ISLANDING = Citation("G.1.i", 148, "the Generating Facility must be Certified as Non-Islanding.")
I_OPTION_4_HOST_LOAD = Threshold(Decimal("0.50"), Citation(
    "G.1.i", 149,
    "This option requires the Generating Facility capacity to be no greater than 50% of Producer's verifiable "
    "minimum Host Load over the past 12 months.",
    interpretation="Gross rating (kW) is used for 'capacity'; it is never smaller than the net rating."))

# --- Screens J, K ---------------------------------------------------------------

J_MAX_KVA = Threshold(Decimal("30"), Citation(
    "G.1.j", 151, "Is the Gross Rating of the Generating Facility 30 kVA or less?"))
J_PASS_ROUTE = Citation("G.1.j", 151, "If Yes (pass), skip Screens K, L and M; Initial Review is complete.")
K_MAX_KW = Threshold(Decimal("500"), Citation(
    "G.1.k", 151,
    "Is the Generating Facility a NEM-1, NEM-2 or NBT-1 Generating Facility with nameplate capacity less than "
    "or equal to 500 kW?"))
K_PASS_ROUTE = Citation("G.1.k", 151, "If Yes (pass), skip screen L and continue to screen M.")

# --- Screen L -------------------------------------------------------------------

L_QUESTION = Citation(
    "G.1.l", 152,
    "Where (i) or (ii) or (iii) or (iv) above are met, the impacts of this Interconnection Request to the "
    "Transmission System may require further Study.")
L_FAIL = Citation("G.1.l", 152, "If Yes (fail), Supplemental Review is required.")

# --- Screen M -------------------------------------------------------------------

M_ICA_FRACTION = Threshold(Decimal("0.90"), Citation(
    "G.1.m", 153,
    "Is the Generating Facility aggregate Gross Nameplate Rating less than or equal to 90% of the lowest value "
    "in the ICA-SG 576 Profile?"))
M_ICA_OF = Citation(
    "G.1.m", 153,
    "Is the Generating Facility aggregate Gross Nameplate Rating less than or equal to 90% of the lowest value "
    "in the ICA-OF 576 Profile?")
M_BOTH_REQUIRED = Citation(
    "G.1.m", 153,
    "If the response is \"yes\" to both a) and b), the Interconnection Request passes Screen M.",
    interpretation="The questions are joined by 'or', but the decision rule requires both; the decision rule is implemented.")
M_FAIL = Citation("G.1.m", 153, "fails Screen M and must be evaluated under the Supplemental Review")
M_FALLBACK_FRACTION = Threshold(Decimal("0.15"), Citation(
    "G.1.m", 154,
    "Is the aggregate Generating Facility capacity on the Line Section less than 15% of Line Section peak load "
    "for all line sections bounded by automatic sectionalizing devices?"))

ALL_CITATIONS: tuple[Citation, ...] = tuple(
    v.citation if isinstance(v, Threshold) else v
    for v in dict(globals()).values()
    if isinstance(v, Citation | Threshold)
)
