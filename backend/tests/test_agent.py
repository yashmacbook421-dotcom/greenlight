from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.agent import Tool, ToolOutcome, run_agent
from app.core.models import AgentRun, AgentStep, Case, Proposal, RuleResult
from app.domains.interconnection.agent.review import draft_deterministic, draft_with_agent, finalize
from app.domains.interconnection.rules.ingest import ingest
from app.domains.interconnection.service import screen_case
from tests.fakes import FakeClient, Script, text_block, tool_use, turn
from tests.test_screening_service import _packet

ECHO = Tool("echo", "echo", {"type": "object", "additionalProperties": False, "required": ["x"],
                             "properties": {"x": {"type": "string"}}})
DONE = Tool("done", "finish", {"type": "object", "additionalProperties": False, "required": ["answer"],
                               "properties": {"answer": {"type": "string"}}}, terminal=True)


def _case(session: Session) -> Case:
    case = Case(domain="interconnection")
    session.add(case)
    session.flush()
    return case


def _run(session: Session, script: Script, *, budget: int = 5, ceiling: str = "1.00", execute=None):
    client = FakeClient(script)
    result = run_agent(session, client, case_id=_case(session).id, model="claude-opus-5", system="s",
                       initial_content=[{"type": "text", "text": "go"}], tools=[ECHO, DONE],
                       execute=execute or (lambda n, a: ToolOutcome({"echo": a["x"]})),
                       step_budget=budget, cost_ceiling_usd=Decimal(ceiling))
    return result, client


# --- the loop ---------------------------------------------------------------------------------------

def test_loop_runs_tools_and_ends_on_the_terminal_tool(session: Session) -> None:
    result, client = _run(session, Script(turn(text_block("checking"), tool_use("echo", {"x": "hi"})),
                                          turn(tool_use("done", {"answer": "42"}))))
    assert result.terminated_by.value == "proposal" and result.terminal_input == {"answer": "42"}
    assert (result.steps_used, result.cost_usd) == (2, Decimal("0.02"))
    steps = session.scalars(select(AgentStep).where(AgentStep.run_id == result.run_id).order_by(AgentStep.n)).all()
    assert [(s.role, s.tool) for s in steps] == [("assistant", None), ("tool", "echo"), ("assistant", None), ("tool", "done")]
    assert steps[1].result == {"content": {"echo": "hi"}, "is_error": False}
    second = client.messages.requests[1]
    assert second["messages"][-1]["content"][0]["type"] == "tool_result"
    assert second["fallbacks"] == "default" and all(t["strict"] for t in second["tools"])
    run = session.get(AgentRun, result.run_id)
    assert run.terminated_by == "proposal" and run.ended_at is not None


def test_step_budget_is_an_outcome_not_a_crash(session: Session) -> None:
    result, _ = _run(session, Script(turn(tool_use("echo", {"x": "again"}))), budget=3)
    assert result.terminated_by.value == "step_budget" and result.steps_used == 3


def test_cost_ceiling_is_checked_before_each_call(session: Session) -> None:
    expensive = turn(tool_use("echo", {"x": "x"}), input_tokens=100_000, output_tokens=0)  # $0.50 per call
    result, client = _run(session, Script(expensive), budget=10, ceiling="1.00")
    assert result.terminated_by.value == "cost_ceiling" and len(client.messages.requests) == 2


def test_model_that_stops_using_tools_gets_one_nudge(session: Session) -> None:
    result, client = _run(session, Script(turn(text_block("done?"), stop_reason="end_turn")))
    assert result.terminated_by.value == "error" and len(client.messages.requests) == 2
    assert "propose_disposition" in client.messages.requests[1]["messages"][-1]["content"][0]["text"]


def test_refusal_ends_the_run(session: Session) -> None:
    result, _ = _run(session, Script(turn(stop_reason="refusal")))
    assert result.terminated_by.value == "error" and "declined" in result.detail


def test_tool_exceptions_are_returned_to_the_model(session: Session) -> None:
    def boom(name, args):
        raise ValueError("bad input")

    result, client = _run(session, Script(turn(tool_use("echo", {"x": "1"})), turn(tool_use("done", {"answer": "ok"}))),
                          execute=boom)
    assert result.terminated_by.value == "proposal"
    sent = client.messages.requests[1]["messages"][-1]["content"][0]
    assert sent["is_error"] is True and "bad input" in sent["content"]


# --- the interconnection review ---------------------------------------------------------------------

@pytest.fixture
def screened(session: Session, tmp_path: Path):
    ingest(session, pdf_path=Path("/nonexistent"))
    case = _packet(session, tmp_path)
    return case, screen_case(session, case)


def test_agent_tools_ground_the_draft_and_guardrails_catch_what_slips(session: Session, screened) -> None:
    case, outcome = screened
    assert outcome.floor.value == "NEEDS_ENGINEER_DETERMINATION"
    script = Script(
        turn(tool_use("run_screens", {"gross_rating_kw": "5", "gross_rating_kva": "5", "exports": None,
                                      "export_option": None, "short_circuit_pu": None, "service_transformer_kva": None,
                                      "rationale": "smaller system"}, id="t1"),
             tool_use("search_rules", {"query": "first notification of deficiency"}, id="t2"),
             tool_use("get_field_provenance", {"field": "applicant_name"}, id="t3"),
             tool_use("flag_deficiency", {"description": "Confirm the applicant", "basis_kind": "discrepancy",
                                          "basis_ref": "applicant_name", "rule_section": "E.5.b.i", "rule_sheet": 70}, id="t4"),
             tool_use("flag_deficiency", {"description": "Invented", "basis_kind": "fact", "basis_ref": "nope",
                                          "rule_section": None, "rule_sheet": None}, id="t5")),
        turn(tool_use("propose_disposition", {
            "disposition": "INITIAL_REVIEW_PASS",
            "letter_markdown": "Approved under Rule 21 §G.1.j (Sheet 151). Your 7.6 kW system is 12.5 kW. See §Z.9 (Sheet 70).",
            "summary_for_engineer": "Looks fine."})),
    )
    draft = draft_with_agent(session, FakeClient(script), case, outcome)
    flag_steps = session.scalars(select(AgentStep).where(AgentStep.tool == "flag_deficiency").order_by(AgentStep.n)).all()
    assert [s.result["is_error"] for s in flag_steps] == [False, True]  # the invented basis was refused at the tool
    assert len(draft.items) == 1
    scenario = session.scalars(select(RuleResult).where(RuleResult.case_id == case.id, RuleResult.overrides != {})).all()
    assert scenario and scenario[0].overrides["rationale"] == "smaller system"

    proposal = finalize(session, case, outcome, draft)
    verdicts = {v["name"]: v for v in proposal.guardrail_verdicts}
    assert proposal.disposition == "NEEDS_ENGINEER_DETERMINATION" and proposal.model_disposition == "INITIAL_REVIEW_PASS"
    assert verdicts["disposition_veto"]["passed"] is False
    assert verdicts["number_faithfulness"]["data"]["unsupported"] == ["12.5"]
    assert "§Z.9 does not exist in the pinned rules" in verdicts["citation_validity"]["detail"]
    assert proposal.status == "pending_review" and proposal.agent_run_id == draft.agent.run_id


def test_agent_that_never_proposes_falls_back_to_the_template(session: Session, screened) -> None:
    case, outcome = screened
    script = Script(turn(tool_use("search_rules", {"query": "Screen J"})))
    draft = draft_with_agent(session, FakeClient(script), case, outcome)
    assert draft.agent.terminated_by.value == "step_budget" and "step budget" in draft.letter
    assert finalize(session, case, outcome, draft).disposition == outcome.floor.value


def test_template_drafts_pass_their_own_guardrails(session: Session, screened) -> None:
    case, outcome = screened
    proposal = finalize(session, case, outcome, draft_deterministic(session, case, outcome, reason="test"))
    failed = [v for v in proposal.guardrail_verdicts if not v["passed"]]
    assert failed == [], failed


def test_the_draft_cannot_be_approved_by_the_pipeline(session: Session, screened) -> None:
    case, outcome = screened
    proposal = finalize(session, case, outcome, draft_deterministic(session, case, outcome))
    with pytest.raises(IntegrityError), session.begin_nested():
        session.execute(update(Proposal).where(Proposal.id == proposal.id).values(status="approved"))
        session.flush()
