"""The thesis, enforced by the database: these writes must be refused."""

import pytest
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.models import Case, Document, ExtractedFact, Page, Proposal, RuleResult
from app.domains.interconnection import DOMAIN

HASH = "0" * 64


def _refused(session: Session, obj=None, stmt=None) -> None:
    with pytest.raises(IntegrityError):
        with session.begin_nested():
            if obj is not None:
                session.add(obj)
            else:
                session.execute(stmt)
            session.flush()


@pytest.fixture
def case(session: Session) -> Case:
    c = Case(domain=DOMAIN, submitter="SunCo Installers")
    session.add(c)
    session.flush()
    return c


@pytest.fixture
def page(session: Session, case: Case) -> Page:
    doc = Document(case=case, kind="application_form", filename="form.pdf", sha256=HASH, page_count=2, storage_uri="s3://x")
    p = Page(document=doc, page_no=1, text="System AC rating: 7.6 kW", has_text_layer=True)
    session.add(p)
    session.flush()
    return p


# --- provenance ---------------------------------------------------------------

def test_fact_with_provenance_is_stored(session: Session, case: Case, page: Page) -> None:
    session.add(ExtractedFact(case_id=case.id, field="ac_rating_kw", value=7.6, unit="kW",
                              document_id=page.document_id, page_no=1, quote="System AC rating: 7.6 kW"))
    session.flush()


def test_fact_citing_nonexistent_page_is_refused(session: Session, case: Case, page: Page) -> None:
    _refused(session, ExtractedFact(case_id=case.id, field="ac_rating_kw", value=7.6,
                                    document_id=page.document_id, page_no=9, quote="7.6 kW"))


def test_fact_with_blank_quote_is_refused(session: Session, case: Case, page: Page) -> None:
    _refused(session, ExtractedFact(case_id=case.id, field="ac_rating_kw", value=7.6,
                                    document_id=page.document_id, page_no=1, quote="   "))


# --- rule results -------------------------------------------------------------

def _result(case: Case, **kw) -> RuleResult:
    base = dict(case_id=case.id, rule_set="sgip_fast_track", rule_id="a", inputs={},
                engine_version="0.1.0", input_hash=HASH)
    return RuleResult(**(base | kw))


def test_uncited_pass_is_refused(session: Session, case: Case) -> None:
    _refused(session, _result(case, status="PASS"))


def test_unclassified_fail_is_refused(session: Session, case: Case) -> None:
    _refused(session, _result(case, status="FAIL", citation=[{"ruleset": "pge_rule21_2025-08-29", "section": "G.1.b", "sheet": 141}]))


def test_inconclusive_without_reason_is_refused(session: Session, case: Case) -> None:
    _refused(session, _result(case, status="INCONCLUSIVE", missing_inputs=["line_section_peak_kw"]))


def test_inconclusive_with_reason_needs_no_citation(session: Session, case: Case) -> None:
    session.add(_result(case, status="INCONCLUSIVE", reason="line_section_peak_kw missing", blocker="utility",
                        missing_inputs=["line_section_peak_kw"]))
    session.flush()


def test_inconclusive_without_blocker_is_refused(session: Session, case: Case) -> None:
    _refused(session, _result(case, status="INCONCLUSIVE", reason="missing", missing_inputs=["x"]))


def test_skipped_without_router_is_refused(session: Session, case: Case) -> None:
    _refused(session, _result(case, status="SKIPPED", citation=[{"section": "G.1.j", "sheet": 151}]))


# --- the human gate -----------------------------------------------------------

def _proposal(case: Case, **kw) -> Proposal:
    return Proposal(**(dict(case_id=case.id, disposition="DEFICIENCY_LETTER", letter_md="Dear applicant") | kw))


def test_proposal_cannot_be_born_approved(session: Session, case: Case) -> None:
    from datetime import UTC, datetime
    _refused(session, _proposal(case, status="approved", reviewed_by="eng", reviewed_at=datetime.now(UTC)))


def test_cannot_approve_without_a_named_reviewer(session: Session, case: Case) -> None:
    p = _proposal(case)
    session.add(p)
    session.flush()
    _refused(session, stmt=update(Proposal).where(Proposal.id == p.id).values(status="approved"))


def test_reviewer_can_approve(session: Session, case: Case) -> None:
    from sqlalchemy import func
    p = _proposal(case)
    session.add(p)
    session.flush()
    session.execute(update(Proposal).where(Proposal.id == p.id)
                    .values(status="approved", reviewed_by="j.engineer", reviewed_at=func.now()))
    session.flush()


def test_approving_a_changed_letter_is_refused(session: Session, case: Case) -> None:
    from sqlalchemy import func
    p = _proposal(case)
    session.add(p)
    session.flush()
    _refused(session, stmt=update(Proposal).where(Proposal.id == p.id).values(
        status="approved", reviewed_by="j.engineer", reviewed_at=func.now(), letter_md="Something else"))


def test_reviewed_proposal_is_immutable(session: Session, case: Case) -> None:
    from sqlalchemy import func
    p = _proposal(case)
    session.add(p)
    session.flush()
    session.execute(update(Proposal).where(Proposal.id == p.id)
                    .values(status="rejected", reviewed_by="j.engineer", reviewed_at=func.now()))
    _refused(session, stmt=update(Proposal).where(Proposal.id == p.id).values(disposition="FAST_TRACK_APPROVE"))
