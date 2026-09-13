import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.models import Document, ExtractedFact, Page
from app.core.storage import LocalStorage
from app.db import get_session
from app.deps import get_storage
from app.main import app
from tests.pdfs import encrypted, image_only_pdf, text_pdf

FORM = text_pdf("INTERCONNECTION APPLICATION\nSystem AC rating: 7.6 kW", "Customer signature: J. Doe")


@pytest.fixture
def client(session: Session, tmp_path: Path) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


@pytest.fixture
def case_id(client: TestClient) -> str:
    r = client.post("/interconnection/applications",
                    json={"utility": "PGE", "submitter": "SunCo Installers", "site_address": "1 Main St"})
    assert r.status_code == 201
    return r.json()["case_id"]


def _upload(client: TestClient, case_id: str, data: bytes, kind: str = "application_form", name: str = "form.pdf"):
    return client.post(f"/cases/{case_id}/documents", data={"kind": kind},
                       files={"file": (name, data, "application/pdf")})


def test_pdf_is_hashed_stored_and_split_into_pages(client, case_id, tmp_path: Path, session: Session) -> None:
    r = _upload(client, case_id, FORM)
    assert r.status_code == 201, r.text
    doc = r.json()

    sha = hashlib.sha256(FORM).hexdigest()
    assert doc["sha256"] == sha
    assert doc["page_count"] == 2
    assert [p["anchor"] for p in doc["pages"]] == [f"{sha[:12]}#p1", f"{sha[:12]}#p2"]
    assert all(p["has_text_layer"] for p in doc["pages"])
    assert (tmp_path / sha[:2] / f"{sha}.pdf").read_bytes() == FORM

    page = client.get(f"/cases/{case_id}/documents/{doc['id']}/pages/1").json()
    assert "System AC rating: 7.6 kW" in page["text"]


def test_stored_page_is_a_valid_provenance_target(client, case_id, session: Session) -> None:
    """The point of intake: extraction can cite (document, page) and the database accepts it."""
    doc = _upload(client, case_id, FORM).json()
    session.add(ExtractedFact(case_id=case_id, field="ac_rating_kw", value=7.6, unit="kW",
                              document_id=doc["id"], page_no=1, quote="System AC rating: 7.6 kW"))
    session.flush()


def test_reupload_of_same_bytes_is_idempotent(client, case_id, session: Session) -> None:
    first = _upload(client, case_id, FORM)
    second = _upload(client, case_id, FORM, name="form-again.pdf")
    assert (first.status_code, second.status_code) == (201, 200)
    assert first.json()["id"] == second.json()["id"]
    assert session.scalar(select(func.count()).select_from(Document).where(Document.case_id == case_id)) == 1


def test_scanned_page_is_kept_and_flagged(client, case_id, session: Session) -> None:
    r = _upload(client, case_id, image_only_pdf(), kind="site_plan")
    assert r.status_code == 201
    assert r.json()["pages"] == [
        {"page_no": 1, "anchor": r.json()["pages"][0]["anchor"], "has_text_layer": False, "char_count": 0}
    ]


def test_datasheet_locked_only_against_editing_is_accepted(client, case_id) -> None:
    locked = encrypted(text_pdf("Inverter model X-7600  Rated AC output 7680 W"), user_password="")
    r = _upload(client, case_id, locked, kind="inverter_spec_sheet")
    assert r.status_code == 201, r.text
    assert r.json()["pages"][0]["has_text_layer"]


@pytest.mark.parametrize(
    ("data", "detail"),
    [
        (b"hello, not a pdf", "not a PDF"),
        (FORM[: len(FORM) // 3], "could not be read"),
        (encrypted(FORM, user_password="secret"), "password-protected"),
    ],
    ids=["not-pdf", "truncated", "password-protected"],
)
def test_unreadable_uploads_are_rejected(client, case_id, session: Session, data: bytes, detail: str) -> None:
    r = _upload(client, case_id, data)
    assert r.status_code == 422
    assert detail in r.json()["detail"]
    assert session.scalar(select(func.count()).select_from(Page).join(Document, Page.document_id == Document.id)
                          .where(Document.case_id == case_id)) == 0


def test_oversized_upload_is_rejected(client, case_id, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_upload_bytes", len(FORM) - 1)
    assert _upload(client, case_id, FORM).status_code == 413


def test_too_many_pages_is_rejected(client, case_id, monkeypatch) -> None:
    monkeypatch.setattr(settings, "max_pages_per_document", 1)
    r = _upload(client, case_id, FORM)
    assert r.status_code == 422 and "limit is 1" in r.json()["detail"]


def test_unknown_document_kind_is_rejected(client, case_id) -> None:
    assert _upload(client, case_id, FORM, kind="selfie").status_code == 422


def test_upload_to_unknown_case_is_404(client) -> None:
    assert _upload(client, "00000000-0000-0000-0000-000000000000", FORM).status_code == 404


def test_case_lists_its_documents(client, case_id) -> None:
    _upload(client, case_id, FORM)
    _upload(client, case_id, image_only_pdf(), kind="site_plan", name="site.pdf")
    case = client.get(f"/cases/{case_id}").json()
    assert case["domain"] == "interconnection"
    assert case["submitter"] == "SunCo Installers"
    assert sorted(d["kind"] for d in case["documents"]) == ["application_form", "site_plan"]
