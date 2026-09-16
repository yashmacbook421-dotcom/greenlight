"""The applicant portal: draft → submit → automatic review → human gate → released letter → corrections → resubmit."""

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.models import Document, ExtractedFact, Notification, Proposal
from app.core.storage import LocalStorage
from app.db import get_session
from app.deps import get_optional_llm_client, get_storage
from app.domains.interconnection.models import InterconnectionApplication
from app.domains.interconnection.rules.ingest import ingest
from app.main import app
from app.routers.portal import get_review_runner, review_submitted
from tests.pdfs import text_pdf

INSTALLER = "Redwood Valley Solar"
PACKET = {"application_form": "Applicant name: Maria Delgado\nSystem AC rating: 7.6 kW",
          "one_line_diagram": "Inverter quantity: 1", "inverter_spec_sheet": "SE7600H-US 32 A"}


@pytest.fixture
def api(session: Session, tmp_path: Path) -> Iterator[TestClient]:
    ingest(session, pdf_path=Path("/nonexistent"))
    storage = LocalStorage(tmp_path)
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: storage
    app.dependency_overrides[get_optional_llm_client] = lambda: None
    app.dependency_overrides[get_review_runner] = lambda: lambda case_id: review_submitted(session, storage, None, case_id)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _start(api: TestClient) -> dict:
    r = api.post("/portal/applications", json={"installer": INSTALLER, "applicant_name": "Maria Delgado",
                                               "site_address": "2147 Brookwood Avenue, Santa Rosa, CA"})
    assert r.status_code == 201
    return r.json()


def _upload(api: TestClient, case_id: str, kind: str, body: str):
    return api.post(f"/portal/applications/{case_id}/documents", data={"kind": kind},
                    files={"file": (f"{kind}.pdf", text_pdf(body), "application/pdf")})


def _submitted(api: TestClient) -> str:
    app_id = _start(api)["id"]
    for kind, body in PACKET.items():
        assert _upload(api, app_id, kind, body).status_code == 201
    r = api.post(f"/portal/applications/{app_id}/submit")
    assert r.status_code == 200, r.text
    return app_id


def _release(api: TestClient, session: Session, case_id: str, disposition: str | None = None) -> None:
    proposal = session.scalars(select(Proposal).where(Proposal.case_id == case_id)
                               .order_by(Proposal.created_at.desc())).first()
    assert proposal is not None and proposal.status == "pending_review"
    if disposition:  # still pending, so the gate allows it; stands in for a particular review outcome
        proposal.disposition = disposition
        session.flush()
    r = api.post(f"/proposals/{proposal.id}/decision", json={"action": "approve", "reviewer": "j.engineer"})
    assert r.status_code == 200


def test_a_draft_is_invisible_to_reviewers_until_submitted(api: TestClient) -> None:
    draft = _start(api)
    assert (draft["status"], draft["can_upload"], draft["can_submit"]) == ("draft", True, False)
    assert "Single-line diagram" in draft["submit_blocker"]
    assert draft["id"] not in {c["case_id"] for c in api.get("/cases").json()}
    assert [a["id"] for a in api.get("/portal/applications", params={"installer": INSTALLER}).json()] == [draft["id"]]
    assert api.get("/portal/applications", params={"installer": "Someone Else"}).json() == []


def test_submit_requires_the_required_documents(api: TestClient) -> None:
    app_id = _start(api)["id"]
    _upload(api, app_id, "application_form", PACKET["application_form"])
    r = api.post(f"/portal/applications/{app_id}/submit")
    assert r.status_code == 409 and "Inverter specification sheet" in r.json()["detail"]


def test_replacing_a_draft_document_keeps_one_current_copy(api: TestClient) -> None:
    app_id = _start(api)["id"]
    _upload(api, app_id, "application_form", "first")
    view = _upload(api, app_id, "application_form", "second").json()
    assert len(view["documents"]) == 1 and view["replaced_documents"] == []
    assert _upload(api, app_id, "application_form", "second").status_code == 200  # identical bytes: no change


def test_submission_reviews_automatically_and_hides_the_draft_letter(api: TestClient, session: Session) -> None:
    app_id = _submitted(api)
    [row] = [c for c in api.get("/cases").json() if c["case_id"] == app_id]
    assert row["status"] == "pending_review" and row["proposal"] is not None and row["submissions"] == 1

    view = api.get(f"/portal/applications/{app_id}").json()
    assert (view["status"], view["letters"], view["can_upload"]) == ("under_review", [], False)
    assert "guardrail_verdicts" not in str(view) and view["submitted_at"] is not None
    assert _upload(api, app_id, "other", "late").status_code == 409


def test_a_rejected_draft_is_still_under_review_for_the_applicant(api: TestClient, session: Session) -> None:
    app_id = _submitted(api)
    proposal = session.scalars(select(Proposal).where(Proposal.case_id == app_id)).one()
    api.post(f"/proposals/{proposal.id}/decision", json={"action": "reject", "reviewer": "j.engineer"})
    view = api.get(f"/portal/applications/{app_id}").json()
    assert view["status"] == "under_review" and view["letters"] == []


def test_deficiency_loop_replaces_documents_and_reviews_again(api: TestClient, session: Session) -> None:
    app_id = _submitted(api)
    _release(api, session, app_id, "DEFICIENCY_NOTICE")

    view = api.get(f"/portal/applications/{app_id}").json()
    assert (view["status"], view["can_upload"], view["can_submit"]) == ("action_required", True, False)
    [letter] = view["letters"]
    assert letter["outcome"] == "action_required" and letter["issued_by"] == "j.engineer" and letter["letter_md"]
    assert api.post(f"/portal/applications/{app_id}/submit").status_code == 409  # nothing corrected yet

    old = session.scalars(select(Document).where(Document.case_id == app_id, Document.kind == "inverter_spec_sheet")).one()
    session.add(ExtractedFact(case_id=old.case_id, document_id=old.id, page_no=1, field="inverter_model",
                              value="SE7600H-US", quote="SE7600H-US", verification="oracle"))
    session.flush()
    view = _upload(api, app_id, "inverter_spec_sheet", "SE7600H-US 32 A fault current 40 A").json()
    assert [d["filename"] for d in view["replaced_documents"]] == ["inverter_spec_sheet.pdf"]
    assert view["can_submit"] and view["timeline"][-1]["label"] == "Corrected document uploaded"
    assert session.scalars(select(ExtractedFact).where(ExtractedFact.document_id == old.id)).all() == []

    assert api.post(f"/portal/applications/{app_id}/submit").json()["status"] == "under_review"
    [row] = [c for c in api.get("/cases").json() if c["case_id"] == app_id]
    assert row["submissions"] == 2 and row["documents"] == 3 and row["proposal"]["status"] == "pending_review"
    bundle = api.get(f"/cases/{app_id}/review").json()
    assert len(bundle["documents"]) == 3 and len(bundle["replaced_documents"]) == 1

    _release(api, session, app_id, "INITIAL_REVIEW_PASS")
    view = api.get(f"/portal/applications/{app_id}").json()
    assert view["status"] == "passed_initial_review" and view["can_upload"] is False
    assert [l["outcome"] for l in view["letters"]] == ["passed_initial_review", "action_required"]
    assert [t["kind"] for t in view["timeline"]][-2:] == ["resubmitted", "decision"]


def test_failed_automatic_review_returns_the_case_to_the_engineer(api: TestClient, session: Session,
                                                                  monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*args, **kwargs):
        raise RuntimeError("extraction service down")
    monkeypatch.setattr("app.routers.portal.review_case", boom)
    app_id = _submitted(api)
    [row] = [c for c in api.get("/cases").json() if c["case_id"] == app_id]
    assert row["status"] == "received" and row["proposal"] is None
    assert api.get(f"/portal/applications/{app_id}").json()["status"] == "under_review"


def test_released_decision_notifies_the_applicant(api: TestClient, session: Session) -> None:
    app_id = _start(api)["id"]  # started without a contact email
    for kind, body in PACKET.items():
        _upload(api, app_id, kind, body)
    api.post(f"/portal/applications/{app_id}/submit")
    session.get(InterconnectionApplication, uuid.UUID(app_id)).contact_email = "dana@example.com"
    session.flush()
    _release(api, session, app_id, "INITIAL_REVIEW_PASS")

    view = api.get(f"/portal/applications/{app_id}").json()
    [notice] = view["notifications"]
    assert notice["kind"] == "decision_released" and notice["recipient"] == "dana@example.com"
    assert notice["status"] == "queued" and notice["sent_at"] is None  # no SMTP configured in tests
    assert "Passed Initial Review" in notice["subject"] and view["reference"] in notice["subject"]

    [stored] = session.scalars(select(Notification).where(Notification.case_id == app_id)).all()
    assert f"/portal/applications/{app_id}" in stored.body and "j.engineer" in stored.body
    assert api.get(f"/cases/{app_id}/review").json()["notifications"][0]["subject"] == notice["subject"]


def test_a_rejected_draft_notifies_nobody(api: TestClient, session: Session) -> None:
    app_id = _submitted(api)
    proposal = session.scalars(select(Proposal).where(Proposal.case_id == app_id)).one()
    api.post(f"/proposals/{proposal.id}/decision", json={"action": "reject", "reviewer": "j.engineer"})
    assert api.get(f"/portal/applications/{app_id}").json()["notifications"] == []


def test_a_decision_without_a_contact_email_is_still_recorded(api: TestClient, session: Session) -> None:
    app_id = _submitted(api)
    _release(api, session, app_id, "DEFICIENCY_NOTICE")
    [notice] = api.get(f"/portal/applications/{app_id}").json()["notifications"]
    assert notice["status"] == "no_recipient" and notice["recipient"] is None
