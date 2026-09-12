"""A stand-in for the Anthropic client: returns scripted responses and records every request."""

from collections.abc import Callable
from types import SimpleNamespace
from typing import Any


def usage(input_tokens: int = 1000, output_tokens: int = 200, cache_read: int = 0, cache_write: int = 0) -> SimpleNamespace:
    return SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens,
                           cache_read_input_tokens=cache_read, cache_creation_input_tokens=cache_write)


class FakeMessages:
    def __init__(self, respond: Callable[[dict[str, Any]], Any]) -> None:
        self.respond = respond
        self.requests: list[dict[str, Any]] = []

    def parse(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        return self.respond(kwargs)

    def create(self, **kwargs: Any) -> Any:
        # Snapshot like a real client that serialises at call time; the caller keeps appending to `messages`.
        kwargs = {**kwargs, "messages": list(kwargs.get("messages", []))}
        self.requests.append(kwargs)
        return self.respond(kwargs)


class FakeClient:
    def __init__(self, respond: Callable[[dict[str, Any]], Any]) -> None:
        self.messages = FakeMessages(respond)
        self.beta = SimpleNamespace(messages=self.messages)


def structured(facts: list[dict[str, Any]], *, stop_reason: str = "end_turn", model: str = "claude-opus-5") -> Callable:
    """Respond with the request's own output_format populated from `facts`."""
    def respond(kwargs: dict[str, Any]) -> Any:
        parsed = kwargs["output_format"].model_validate({"facts": facts}) if stop_reason == "end_turn" else None
        return SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason, usage=usage(), model=model,
                               _request_id="req_test", stop_details=SimpleNamespace(category=None))
    return respond


def fact(field: str, value: str, unit: str | None, page: int, quote: str, instance: str | None = None) -> dict[str, Any]:
    return {"field": field, "instance": instance, "value_as_written": value, "unit_as_written": unit,
            "page": page, "quote": quote}


def tool_use(name: str, input: dict[str, Any], id: str | None = None) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id or f"toolu_{name}", name=name, input=input)


def text_block(text: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=text)


def turn(*blocks: Any, stop_reason: str = "tool_use", model: str = "claude-opus-5", **usage_kw: int) -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason=stop_reason, usage=usage(**usage_kw), model=model,
                           _request_id="req_agent", stop_details=None)


class Script:
    """Agent responses in order; repeats the last one when exhausted."""

    def __init__(self, *turns: Any) -> None:
        self.turns = list(turns)
        self.i = 0

    def __call__(self, kwargs: dict[str, Any]) -> Any:
        t = self.turns[min(self.i, len(self.turns) - 1)]
        self.i += 1
        return t(kwargs) if callable(t) else t
