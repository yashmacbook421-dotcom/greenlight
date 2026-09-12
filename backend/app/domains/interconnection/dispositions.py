import enum


class Disposition(enum.StrEnum):
    """Each maps to a written notice PG&E Electric Rule 21 requires (see rules/manifest.json)."""

    DEFICIENCY_NOTICE = "DEFICIENCY_NOTICE"  # §E.5.b.i, Sheet 70 — request not complete and valid
    INITIAL_REVIEW_PASS = "INITIAL_REVIEW_PASS"  # §F.1.b, Sheet 78 — passed Screens A–M
    SUPPLEMENTAL_REVIEW_REQUIRED = "SUPPLEMENTAL_REVIEW_REQUIRED"  # §F.2.a, Sheet 83 — failed Initial Review
    NEEDS_ENGINEER_DETERMINATION = "NEEDS_ENGINEER_DETERMINATION"  # utility-only input or practice missing
