from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.extraction import (
    AcceptedFact,
    Candidate,
    RejectedFact,
    Rejection,
    Verification,
    extract_document,
    verify,
)
from app.core.intake import ingest_document
from app.core.llm import FALLBACK_BETA, LLMRefused, LLMTruncated, cost_usd
from app.core.models import Case, ExtractedFact
from app.core.storage import LocalStorage
from app.db import get_session
from app.deps import get_llm_client, get_storage
from app.domains.interconnection import DOMAIN
from app.domains.interconnection.extraction_fields import FIELDS
from app.main import app
from tests.fakes import FakeClient, fact, structured
from tests.pdfs import image_only_pdf, text_pdf

SPECS = {s.name: s for s in FIELDS}
SPEC_SHEET = "X-7600 Inverter Datasheet\nRated AC output power 7,680 W\nMax continuous output current 32 A\n" \
             "Max output fault current 38.4 A\nListed to UL 1741 SB"
PAGES = {1: (SPEC_SHEET, True), 2: ("", False)}


def check(field: str, value: str, unit: str | None, quote: str, page: int = 1) -> AcceptedFact | RejectedFact:
    return verify(Candidate(field, value, unit, page, quote), SPECS, PAGES)


# --- verification rules --------------------------------------------------------------------

def test_number_with_thousands_separator_is_converted_to_canonical_unit() -> None:
    r = check("inverter_rated_ac_power", "7,680", "W", "Rated AC output power 7,680 W")
    assert isinstance(r, AcceptedFact)
    assert (r.value, r.unit, r.verification) == ("7.68", "kW", Verification.TEXT_MATCH)


def test_quote_must_be_on_the_cited_page() -> None:
    r = check("inverter_rated_ac_power", "7,600", "W", "Rated AC output power 7,600 W")
    assert isinstance(r, RejectedFact) and r.reason is Rejection.QUOTE_NOT_ON_PAGE


def test_quote_matching_tolerates_whitespace_and_case() -> None:
    r = check("inverter_max_fault_current", "38.4", "A", "max OUTPUT fault\ncurrent   38.4 A")
    assert isinstance(r, AcceptedFact) and r.value == "38.4"


@pytest.mark.parametrize(("value", "reason"), [
    ("7.6", Rejection.VALUE_NOT_IN_QUOTE),      # 7.6 must not match inside 7.68 / 7,680
    ("768", Rejection.VALUE_NOT_IN_QUOTE),
    ("seven", Rejection.VALUE_NOT_NUMERIC),
])
def test_number_must_appear_literally_in_quote(value: str, reason: Rejection) -> None:
    r = check("inverter_rated_ac_power", value, "W", "Rated AC output power 7,680 W")
    assert isinstance(r, RejectedFact) and r.reason is reason


@pytest.mark.parametrize(("unit", "reason"), [
    (None, Rejection.UNIT_MISSING),
    ("kW", Rejection.UNIT_NOT_IN_QUOTE),        # a 1000x error the model cannot sneak through
    ("hp", Rejection.UNIT_NOT_ALLOWED),
])
def test_unit_rules(unit: str | None, reason: Rejection) -> None:
    r = check("inverter_rated_ac_power", "7,680", unit, "Rated AC output power 7,680 W")
    assert isinstance(r, RejectedFact) and r.reason is reason


def test_unit_must_match_the_fields_family() -> None:
    r = check("inverter_max_fault_current", "7,680", "W", "Rated AC output power 7,680 W")
    assert isinstance(r, RejectedFact) and r.reason is Rejection.UNIT_NOT_ALLOWED


def test_text_value_must_be_in_quote_and_choice_must_be_allowed() -> None:
    assert isinstance(check("inverter_certification", "UL 1741 SB", None, "Listed to UL 1741 SB"), AcceptedFact)
    bad = check("inverter_certification", "IEEE 1547-2018", None, "Listed to UL 1741 SB")
    assert isinstance(bad, RejectedFact) and bad.reason is Rejection.VALUE_NOT_IN_QUOTE
    choice = check("export_intent", "maybe", None, "Listed to UL 1741 SB")
    assert isinstance(choice, RejectedFact) and choice.reason is Rejection.CHOICE_NOT_ALLOWED


def test_count_fields_take_no_unit() -> None:
    r = verify(Candidate("inverter_quantity", "2", None, 1, "Listed"), SPECS, {1: ("Qty 2 Listed", True)})
    assert isinstance(r, RejectedFact) and r.reason is Rejection.VALUE_NOT_IN_QUOTE
    r = verify(Candidate("inverter_quantity", "2", None, 1, "Qty 2"), SPECS, {1: ("Qty 2 Listed", True)})
    assert isinstance(r, AcceptedFact) and r.value == "2"


def test_scanned_page_facts_are_kept_but_marked_unverified() -> None:
    r = check("service_panel_rating", "200", "A", "Main panel 200 A", page=2)
    assert isinstance(r, AcceptedFact) and r.verification is Verification.IMAGE_UNVERIFIED


def test_unknown_page_and_field() -> None:
    assert check("service_panel_rating", "200", "A", "200 A", page=9).reason is Rejection.UNKNOWN_PAGE  # type: ignore[union-attr]
    assert check("favourite_colour", "blue", None, "blue").reason is Rejection.UNKNOWN_FIELD  # type: ignore[union-attr]


def test_cost_uses_cache_multipliers() -> None:
    assert cost_usd("claude-opus-5", input_tokens=1_000_000, output_tokens=0) == Decimal("5")
    assert cost_usd("claude-opus-5", input_tokens=0, output_tokens=0, cache_read_input_tokens=1_000_000) == Decimal("0.5")
    assert cost_usd("claude-opus-5", input_tokens=0, output_tokens=0, cache_creation_input_tokens=1_000_000) == Decimal("6.25")
    assert cost_usd("some-unpriced-model", input_tokens=1, output_tokens=1) is None


# --- end to end with a scripted model ------------------------------------------------------------

@pytest.fixture
def storage(tmp_path: Path) -> LocalStorage:
    return LocalStorage(tmp_path)


@pytest.fixture
def packet(session: Session, storage: LocalStorage):
    case = Case(domain=DOMAIN)
    session.add(case)
    session.flush()
    spec, _ = ingest_document(session, storage, case_id=case.id, kind="inverter_spec_sheet", filename="spec.pdf",
                              data=text_pdf(SPEC_SHEET), max_pages=10)
    scan, _ = ingest_document(session, storage, case_id=case.id, kind="site_plan", filename="site.pdf",
                              data=image_only_pdf(), max_pages=10)
    return case, spec, scan


def test_extract_persists_only_verified_facts(session: Session, storage: LocalStorage, packet) -> None:
    case, spec, _ = packet
    client = FakeClient(structured([
        fact("inverter_rated_ac_power", "7,680", "W", 1, "Rated AC output power 7,680 W"),
        fact("inverter_max_fault_current", "38.4", "A", 1, "Max output fault current 38.4 A"),
        fact("inverter_rated_ac_power", "7,600", "W", 1, "Rated AC output power 7,600 W"),  # hallucinated
    ]))
    result = extract_document(session, client, storage, spec, FIELDS, model="claude-opus-5", max_tokens=4000)

    assert [f.candidate.field for f in result.accepted] == ["inverter_rated_ac_power", "inverter_max_fault_current"]
    assert [r.reason for r in result.rejected] == [Rejection.QUOTE_NOT_ON_PAGE]
    rows = session.scalars(select(ExtractedFact).where(ExtractedFact.document_id == spec.id)).all()
    assert {(r.field, r.value, r.unit, r.value_as_written) for r in rows} == {
        ("inverter_rated_ac_power", "7.68", "kW", "7,680"), ("inverter_max_fault_current", "38.4", "A", "38.4")}
    assert all(r.extracted_by == "claude-opus-5" and r.verification == "text_match" for r in rows)
    assert result.call is not None and result.call.cost_usd == Decimal("0.01")  # 1000 in @ $5 + 200 out @ $25 per MTok

    request = client.messages.requests[0]
    assert request["model"] == "claude-opus-5"
    assert request["fallbacks"] == "default" and request["betas"] == [FALLBACK_BETA]
    assert request["system"][0]["cache_control"] == {"type": "ephemeral"}
    assert all(b["type"] == "text" for b in request["messages"][0]["content"])  # text-layer PDF: no document blocks


def test_reextraction_replaces_earlier_facts(session: Session, storage: LocalStorage, packet) -> None:
    _, spec, _ = packet
    first = FakeClient(structured([fact("inverter_max_fault_current", "38.4", "A", 1, "Max output fault current 38.4 A")]))
    extract_document(session, first, storage, spec, FIELDS, model="claude-opus-5", max_tokens=4000)
    extract_document(session, FakeClient(structured([])), storage, spec, FIELDS, model="claude-opus-5", max_tokens=4000)
    assert session.scalars(select(ExtractedFact).where(ExtractedFact.document_id == spec.id)).all() == []


def test_scanned_pages_are_sent_as_single_page_pdfs(session: Session, storage: LocalStorage, packet) -> None:
    _, _, scan = packet
    client = FakeClient(structured([fact("service_panel_rating", "200", "A", 1, "Main panel 200 A")]))
    result = extract_document(session, client, storage, scan, FIELDS, model="claude-opus-5", max_tokens=4000)
    blocks = client.messages.requests[0]["messages"][0]["content"]
    docs = [b for b in blocks if b["type"] == "document"]
    assert len(docs) == 1 and docs[0]["title"] == "page 1" and docs[0]["source"]["media_type"] == "application/pdf"
    assert result.accepted[0].verification is Verification.IMAGE_UNVERIFIED


@pytest.mark.parametrize(("stop", "error"), [("refusal", LLMRefused), ("max_tokens", LLMTruncated)])
def test_refusal_and_truncation_store_nothing(session: Session, storage: LocalStorage, packet, stop: str, error) -> None:
    _, spec, _ = packet
    with pytest.raises(error):
        extract_document(session, FakeClient(structured([], stop_reason=stop)), storage, spec, FIELDS,
                         model="claude-opus-5", max_tokens=4000)
    assert session.scalars(select(ExtractedFact).where(ExtractedFact.document_id == spec.id)).all() == []


def test_prompt_marks_document_text_as_data_not_instructions() -> None:
    from app.core.extraction import system_prompt
    prompt = system_prompt(FIELDS)
    assert "not followed" in prompt and "tariff_program" in prompt and "NBT-1" in prompt


# --- API --------------------------------------------------------------------------------------------

@pytest.fixture
def api(session: Session, storage: LocalStorage) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_storage] = lambda: storage
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_extract_endpoint(api: TestClient, packet) -> None:
    case, spec, _ = packet
    app.dependency_overrides[get_llm_client] = lambda: FakeClient(structured([
        fact("inverter_rated_ac_power", "7,680", "W", 1, "Rated AC output power 7,680 W"),
        fact("inverter_rated_ac_power", "9,999", "W", 1, "Rated AC output power 9,999 W"),
    ]))
    body = api.post(f"/cases/{case.id}/documents/{spec.id}/extract").json()
    assert [(f["field"], f["value"], f["unit"]) for f in body["accepted"]] == [("inverter_rated_ac_power", "7.68", "kW")]
    assert body["rejected"][0]["reason"] == "quote_not_on_page"
    assert body["cost_usd"] == "0.01"


def test_extract_endpoint_without_credentials_is_503(api: TestClient, packet, monkeypatch) -> None:
    import anthropic

    import app.deps as deps

    def no_credentials():
        raise anthropic.AnthropicError("no credentials")

    monkeypatch.setattr(deps, "default_client", no_credentials)
    case, spec, _ = packet
    assert api.post(f"/cases/{case.id}/documents/{spec.id}/extract").status_code == 503


def test_default_client_refuses_to_start_without_credentials(monkeypatch) -> None:
    import anthropic

    from app.core.llm import default_client
    from app.deps import get_optional_llm_client
    for var in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("HOME", "/nonexistent-home")
    with pytest.raises(anthropic.AnthropicError):
        default_client()
    assert get_optional_llm_client() is None  # the review pipeline falls back to deterministic drafting


def test_metered_client_attributes_cost_to_stages() -> None:
    from app.core.llm import MeteredClient
    from tests.fakes import tool_use, turn

    def respond(kwargs):
        if "tools" in kwargs:
            return turn(tool_use("done", {}))
        return structured([])(kwargs)

    metered = MeteredClient(FakeClient(respond))
    from app.core.extraction import _output_model
    metered.beta.messages.parse(output_format=_output_model(FIELDS), messages=[])
    metered.beta.messages.create(tools=[{}], messages=[])
    assert metered.by_stage == {"Extraction": Decimal("0.01"), "agent": Decimal("0.01")}
    assert metered.cost_usd == Decimal("0.02") and len(metered.calls) == 2
