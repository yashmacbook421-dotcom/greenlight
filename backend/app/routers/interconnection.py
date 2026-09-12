from fastapi import APIRouter, status

from app.core.models import Case
from app.deps import SessionDep
from app.domains.interconnection import DOMAIN
from app.domains.interconnection.models import InterconnectionApplication
from app.domains.interconnection.schemas import ApplicationCreate, ApplicationCreated

router = APIRouter(prefix="/interconnection", tags=["interconnection"])


@router.post("/applications", response_model=ApplicationCreated, status_code=status.HTTP_201_CREATED)
def create_application(body: ApplicationCreate, session: SessionDep) -> ApplicationCreated:
    """Open a case. Documents are then uploaded to /cases/{case_id}/documents."""
    case = Case(domain=DOMAIN, submitter=body.submitter)
    session.add(case)
    session.flush()
    session.add(InterconnectionApplication(
        case_id=case.id, utility=body.utility, applicant_name=body.applicant_name, site_address=body.site_address,
    ))
    session.commit()
    return ApplicationCreated(case_id=case.id, status=case.status)
