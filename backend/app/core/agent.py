"""A bounded tool-use loop, written out by hand: the control flow is part of what gets reviewed.

- One step = one model call. The step budget and the cost ceiling are checked *before* each call.
- The loop ends only when a terminal tool is called, the budget or ceiling is reached, or the model
  cannot continue (refusal, truncation, repeated refusal to use tools). Nothing else ends it.
- Every assistant turn and tool execution is written to agent_steps with tokens, cost and latency,
  so a review can be replayed months later.
- Tool inputs are schema-validated by the API (`strict: true`); tool *effects* are the executor's job.
"""

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.orm import Session

from app.core.llm import FALLBACK_BETA, CallRecord, MessagesClient
from app.core.models import AgentRole, AgentRun, AgentStep, AgentTermination


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    terminal: bool = False

    def definition(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.input_schema, "strict": True}


@dataclass(frozen=True)
class ToolOutcome:
    content: Any  # JSON-serialisable
    is_error: bool = False


Executor = Callable[[str, dict[str, Any]], ToolOutcome]


@dataclass
class AgentResult:
    run_id: uuid.UUID
    terminated_by: AgentTermination
    terminal_input: dict[str, Any] | None
    steps_used: int
    cost_usd: Decimal
    detail: str | None = None
    tool_results: list[dict[str, Any]] = field(default_factory=list)


NUDGE = "Finish the review by calling propose_disposition."


def _block(b: Any) -> dict[str, Any]:
    if isinstance(b, dict):
        return b
    if hasattr(b, "model_dump"):
        return b.model_dump(mode="json")
    return {k: v for k, v in vars(b).items() if not k.startswith("_")}


def _trace_block(b: dict[str, Any]) -> dict[str, Any]:
    if b.get("type") == "thinking":
        return {"type": "thinking"}  # thinking text is not returned by the API; keep the marker only
    return b


def run_agent(
    session: Session,
    client: MessagesClient,
    *,
    case_id: uuid.UUID,
    model: str,
    system: str,
    initial_content: list[dict[str, Any]],
    tools: list[Tool],
    execute: Executor,
    step_budget: int,
    cost_ceiling_usd: Decimal,
    max_tokens: int = 16000,
    effort: str | None = None,
    max_nudges: int = 1,
) -> AgentResult:
    run = AgentRun(case_id=case_id, model=model, step_budget=step_budget, cost_ceiling_usd=cost_ceiling_usd)
    session.add(run)
    session.flush()

    terminal = {t.name for t in tools if t.terminal}
    definitions = [t.definition() for t in tools]
    messages: list[dict[str, Any]] = [{"role": "user", "content": initial_content}]
    n = 0
    nudges = 0
    tool_log: list[dict[str, Any]] = []

    def record(**kw: Any) -> None:
        nonlocal n
        n += 1
        session.add(AgentStep(run_id=run.id, n=n, **kw))

    def finish(how: AgentTermination, terminal_input: dict[str, Any] | None = None, detail: str | None = None) -> AgentResult:
        run.terminated_by = how.value
        run.ended_at = datetime.now(UTC)
        session.flush()
        return AgentResult(run.id, how, terminal_input, run.steps_used, run.cost_usd, detail, tool_log)

    while True:
        if run.steps_used >= step_budget:
            return finish(AgentTermination.STEP_BUDGET, detail=f"step budget of {step_budget} model calls exhausted")
        if run.cost_usd >= cost_ceiling_usd:
            return finish(AgentTermination.COST_CEILING, detail=f"cost ceiling of ${cost_ceiling_usd} reached")

        kwargs: dict[str, Any] = {
            "model": model, "max_tokens": max_tokens, "system": system, "tools": definitions, "messages": messages,
            "cache_control": {"type": "ephemeral"}, "betas": [FALLBACK_BETA], "fallbacks": "default",
        }
        if effort:
            kwargs["output_config"] = {"effort": effort}
        started = time.monotonic()
        response = client.beta.messages.create(**kwargs)
        latency_ms = int((time.monotonic() - started) * 1000)
        call = CallRecord.from_response(response)
        run.steps_used += 1
        run.cost_usd += call.cost_usd if call.cost_usd is not None else Decimal(0)
        content = [_block(b) for b in response.content]
        record(role=AgentRole.ASSISTANT.value, result={"stop_reason": response.stop_reason, "model": call.model,
                                                        "request_id": call.request_id,
                                                        "content": [_trace_block(b) for b in content]},
               input_tokens=call.input_tokens + call.cache_read_input_tokens + call.cache_creation_input_tokens,
               output_tokens=call.output_tokens, cost_usd=call.cost_usd, latency_ms=latency_ms)
        if call.cost_usd is None:
            session.flush()
            return finish(AgentTermination.ERROR, detail=f"no price for serving model {call.model}; cost cannot be bounded")

        if response.stop_reason == "refusal":
            return finish(AgentTermination.ERROR, detail="model declined the request")
        if response.stop_reason == "max_tokens":
            return finish(AgentTermination.ERROR, detail="model output truncated at max_tokens")

        # Append the assistant turn unchanged (thinking blocks must be replayed as-is).
        messages.append({"role": "assistant", "content": response.content})
        uses = [b for b in content if b.get("type") == "tool_use"]
        if not uses:
            if nudges >= max_nudges:
                return finish(AgentTermination.ERROR, detail="model ended its turn without proposing a disposition")
            nudges += 1
            messages.append({"role": "user", "content": [{"type": "text", "text": NUDGE}]})
            continue

        results = []
        proposal: dict[str, Any] | None = None
        for use in uses:
            name, args = use["name"], use.get("input") or {}
            if name in terminal:
                if proposal is None:
                    proposal = args
                    record(role=AgentRole.TOOL.value, tool=name, args=args, result={"accepted": True})
                    results.append({"type": "tool_result", "tool_use_id": use["id"], "content": "Proposal recorded."})
                continue
            started = time.monotonic()
            try:
                outcome = execute(name, args)
            except Exception as exc:  # a tool failure is information for the model, not a crash
                outcome = ToolOutcome({"error": f"{type(exc).__name__}: {exc}"}, is_error=True)
            record(role=AgentRole.TOOL.value, tool=name, args=args,
                   result={"content": outcome.content, "is_error": outcome.is_error},
                   latency_ms=int((time.monotonic() - started) * 1000))
            tool_log.append({"tool": name, "args": args, "content": outcome.content, "is_error": outcome.is_error})
            results.append({"type": "tool_result", "tool_use_id": use["id"],
                            "content": json.dumps(outcome.content, default=str), "is_error": outcome.is_error})
        session.flush()
        if proposal is not None:
            return finish(AgentTermination.PROPOSAL, terminal_input=proposal)
        messages.append({"role": "user", "content": results})
