"""What an applicant is told about their interconnection application: outcome wording and the decision notice.

Kept out of the router so the human gate can send the same notice the portal shows, without importing a router.
"""

import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.core.models import Case, Proposal
from app.domains.interconnection.dispositions import Disposition
from app.domains.interconnection.models import InterconnectionApplication

# code, label, and the sentence explaining what it means for the applicant
OUTCOMES: dict[Disposition, tuple[str, str, str]] = {
    Disposition.INITIAL_REVIEW_PASS: (
        "passed_initial_review", "Passed Initial Review",
        "The system passed the Rule 21 Initial Review screens. The utility will contact you about next steps."),
    Disposition.DEFICIENCY_NOTICE: (
        "action_required", "Action required",
        "The utility found problems with the application. Read the notice, upload corrected documents, and resubmit."),
    Disposition.SUPPLEMENTAL_REVIEW_REQUIRED: (
        "supplemental_review", "Supplemental Review required",
        "At least one Initial Review screen did not pass, so the application moves to Supplemental Review."),
    Disposition.NEEDS_ENGINEER_DETERMINATION: (
        "engineering_review", "Engineering review",
        "A utility engineer needs to make a determination before the review can finish. See the letter for details."),
}
DRAFT = ("draft", "Draft", "Not submitted yet. Upload the required documents, then submit.")
UNDER_REVIEW = ("under_review", "Under review", "The utility is reviewing the application. The decision will appear here.")

DECISION_RELEASED = "decision_released"


def reference(case_id: uuid.UUID) -> str:
    return f"GL-{case_id.hex[:8].upper()}"


def application_url(case_id: uuid.UUID) -> str:
    return f"{settings.portal_base_url.rstrip('/')}/portal/applications/{case_id}"


def decision_notice(session: Session, case: Case, proposal: Proposal) -> tuple[str | None, str, str]:
    """The notice for a decision an engineer has just released: (recipient, subject, body)."""
    app = session.get(InterconnectionApplication, case.id)
    _, label, detail = OUTCOMES[Disposition(proposal.disposition)]
    ref = reference(case.id)
    site = (app.site_address if app else None) or "your site"
    greeting = case.submitter or (app.applicant_name if app else None) or "applicant"
    body = (
        f"Hello {greeting},\n\n"
        f"There is a decision on interconnection application {ref} for {site}.\n\n"
        f"{label}\n{detail}\n\n"
        f"The full letter, and anything you need to do next, is in the portal:\n{application_url(case.id)}\n\n"
        f"Reviewed by {proposal.reviewed_by}.\n\n"
        "— Greenlight interconnection review (demonstration system; not a PG&E notice)\n"
    )
    return (app.contact_email if app else None), f"{ref}: {label}", body
