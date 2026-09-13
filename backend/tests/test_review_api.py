from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.storage import LocalStorage
from app.db import get_session
from app.deps import get_optional_llm_client, get_storage
from app.domains.interconnection.rules.ingest import ingest
from app.main import app
from tests.fakes import FakeClient, Script, tool_use, turn, usage
from tests.test_screening_service import _packet


@pytest.fixture
def api(session: Session, tmp_path: Path) -> Iterator[TestClient]:
    ingest(session, pdf_path=Path("/nonexistent"))
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: LocalStorage(tmp_path)
    app.dependency_overrides[get_optional_llm_client] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def case_id(session: Session, tmp_path: Path) -> str:
    return str(_packet(session, tmp_path).id)


def test_review_without_claude_drafts_deterministically_and_waits_for_a_human(api: TestClient, case_id: str) -> None:
    body = api.post(f"/cases/{case_id}/review").json()
    assert body["llm_used"] is False
    proposal = body["proposal"]
    assert proposal["status"] == "pending_review" and proposal["agent_run_id"] is None
    assert "no Claude API client configured" in proposal["letter_md"]

    [row] = [c for c in api.get("/cases").json() if c["case_id"] == case_id]
    assert row["status"] == "pending_review" and row["proposal"]["disposition"] == proposal["disposition"]

    bundle = api.get(f"/cases/{case_id}/review").json()
    assert len(bundle["screens"]) == 14 and bundle["facts"] and bundle["documents"]
    assert bundle["discrepancies"][0]["field"] == "applicant_name"
    assert all(c["sheet"] for s in bundle["screens"] for c in s["citations"])
    assert api.get(f"/cases/{case_id}/trace").json() == []


def test_human_gate_approve_then_locked(api: TestClient, case_id: str) -> None:
    proposal = api.post(f"/cases/{case_id}/review").json()["proposal"]
    approved = api.post(f"/proposals/{proposal['id']}/decision", json={"action": "approve", "reviewer": "j.engineer"})
    assert approved.status_code == 200 and approved.json()["status"] == "approved"
    again = api.post(f"/proposals/{proposal['id']}/decision", json={"action": "reject", "reviewer": "someone"})
    assert again.status_code == 409


def test_edit_requires_the_revised_letter(api: TestClient, case_id: str) -> None:
    proposal = api.post(f"/cases/{case_id}/review").json()["proposal"]
    url = f"/proposals/{proposal['id']}/decision"
    assert api.post(url, json={"action": "edit", "reviewer": "j.engineer"}).status_code == 422
    edited = api.post(url, json={"action": "edit", "reviewer": "j.engineer", "letter_md": "Revised.", "note": "tone"}).json()
    assert (edited["status"], edited["letter_md"], edited["review_note"]) == ("edited", "Revised.", "tone")


def test_anonymous_decision_is_rejected(api: TestClient, case_id: str) -> None:
    proposal = api.post(f"/cases/{case_id}/review").json()["proposal"]
    assert api.post(f"/proposals/{proposal['id']}/decision", json={"action": "approve", "reviewer": ""}).status_code == 422


def test_original_document_is_one_click_away(api: TestClient, case_id: str) -> None:
    doc = api.get(f"/cases/{case_id}/review").json()["documents"][0]
    r = api.get(f"/cases/{case_id}/documents/{doc['id']}/file")
    assert r.status_code == 200 and r.content.startswith(b"%PDF") and r.headers["content-type"] == "application/pdf"


def test_review_with_claude_records_a_trace(api: TestClient, case_id: str) -> None:
    def judge_or_agent(kwargs):
        if "tools" in kwargs:
            return Script(turn(tool_use("propose_disposition", {
                "disposition": "NEEDS_ENGINEER_DETERMINATION",
                "letter_markdown": "Engineer: confirm the applicant name conflict.",
                "summary_for_engineer": "Name conflict."})))(kwargs)
        fmt = kwargs["output_format"]
        payload = {"judgments": [{"conflict_index": 0, "material": False, "rationale": "Same household."}]} \
            if "judgments" in fmt.model_fields else {"facts": []}
        return SimpleNamespace(parsed_output=fmt.model_validate(payload), stop_reason="end_turn", usage=usage(),
                               model="claude-opus-5", _request_id="r", stop_details=None)

    app.dependency_overrides[get_optional_llm_client] = lambda: FakeClient(judge_or_agent)
    body = api.post(f"/cases/{case_id}/review").json()
    assert body["llm_used"] is True and body["proposal"]["agent_run_id"]
    [run] = api.get(f"/cases/{case_id}/trace").json()
    assert run["terminated_by"] == "proposal" and [s["role"] for s in run["steps"]] == ["assistant", "tool"]


def test_demo_packet_with_oracle_facts_reviews_end_to_end(api: TestClient) -> None:
    created = api.post("/demo/packets", json={"family": "uncertified_inverter", "seed": 3, "oracle_facts": True}).json()
    review = api.post(f"/cases/{created['case_id']}/review").json()
    assert review["proposal"]["disposition"] == created["expected_disposition"] == "SUPPLEMENTAL_REVIEW_REQUIRED"
    assert api.post("/demo/packets", json={"family": "nope"}).status_code == 422


def test_cors_allows_the_frontend(api: TestClient) -> None:
    r = api.options("/cases", headers={"Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:3000"
