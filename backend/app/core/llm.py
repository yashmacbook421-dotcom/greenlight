"""The one place the backend talks to Claude.

Nothing under app/domains/*/screens may import this module (asserted by test).
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import anthropic

# USD per million tokens. Cache writes (5-minute TTL) bill at 1.25x input, cache reads at 0.1x.
PRICING_PER_MTOK: dict[str, tuple[Decimal, Decimal]] = {
    "claude-opus-5": (Decimal("5"), Decimal("25")),
    "claude-opus-4-8": (Decimal("5"), Decimal("25")),  # possible server-side fallback target
}
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class LLMError(RuntimeError):
    pass


class LLMRefused(LLMError):
    """The model (and any server-side fallback) declined the request."""


class LLMTruncated(LLMError):
    """Output hit max_tokens; a partial structured response is never used."""


class MessagesClient(Protocol):
    """The slice of the Anthropic client we use; tests pass a fake with the same shape."""

    @property
    def beta(self) -> Any: ...


@dataclass(frozen=True)
class CallRecord:
    model: str
    request_id: str | None
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int
    cache_read_input_tokens: int
    cost_usd: Decimal | None  # None when the serving model has no price entry

    @classmethod
    def from_response(cls, response: Any) -> "CallRecord":
        u = response.usage
        tokens = {
            "input_tokens": u.input_tokens or 0,
            "output_tokens": u.output_tokens or 0,
            "cache_creation_input_tokens": getattr(u, "cache_creation_input_tokens", None) or 0,
            "cache_read_input_tokens": getattr(u, "cache_read_input_tokens", None) or 0,
        }
        return cls(model=response.model, request_id=getattr(response, "_request_id", None),
                   cost_usd=cost_usd(response.model, **tokens), **tokens)


def cost_usd(model: str, *, input_tokens: int, output_tokens: int, cache_creation_input_tokens: int = 0,
             cache_read_input_tokens: int = 0) -> Decimal | None:
    price = PRICING_PER_MTOK.get(model)
    if price is None:
        return None
    inp, out = price
    total = (inp * input_tokens + out * output_tokens
             + inp * Decimal("1.25") * cache_creation_input_tokens + inp * Decimal("0.1") * cache_read_input_tokens)
    return total / Decimal(1_000_000)


def default_client() -> anthropic.Anthropic:
    """A client with resolvable credentials, or AnthropicError.

    The SDK constructs a client without credentials and only fails on the first request; checking here lets
    callers fall back (e.g. to deterministic drafting) instead of failing mid-review.
    """
    client = anthropic.Anthropic()
    if not (client.api_key or client.auth_token or client.credentials):
        raise anthropic.AnthropicError("no Claude API credentials found (set ANTHROPIC_API_KEY or run `ant auth login`)")
    return client


def parse_structured(client: MessagesClient, *, model: str, max_tokens: int, effort: str | None,
                     system: list[dict[str, Any]], content: list[dict[str, Any]], output_format: type) -> tuple[Any, CallRecord]:
    """One structured-output call with server-side refusal fallback. Returns (parsed_output, record)."""
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_format": output_format,
        "betas": [FALLBACK_BETA],
        "fallbacks": "default",
    }
    if effort:
        kwargs["output_config"] = {"effort": effort}
    response = client.beta.messages.parse(**kwargs)
    record = CallRecord.from_response(response)
    if response.stop_reason == "refusal":
        category = getattr(getattr(response, "stop_details", None), "category", None)
        raise LLMRefused(f"model declined (category={category}, request_id={record.request_id})")
    if response.stop_reason == "max_tokens":
        raise LLMTruncated(f"output truncated at max_tokens={max_tokens} (request_id={record.request_id})")
    if response.parsed_output is None:
        raise LLMError(f"no structured output (stop_reason={response.stop_reason}, request_id={record.request_id})")
    return response.parsed_output, record


class MeteredClient:
    """Wraps a client and totals the cost of every call made through it (extraction, judge, agent)."""

    def __init__(self, inner: MessagesClient) -> None:
        self._inner = inner
        self.calls: list[CallRecord] = []
        meter = self

        class _Messages:
            def parse(self, **kwargs: Any) -> Any:
                response = inner.beta.messages.parse(**kwargs)
                meter.calls.append(CallRecord.from_response(response))
                return response

            def create(self, **kwargs: Any) -> Any:
                response = inner.beta.messages.create(**kwargs)
                meter.calls.append(CallRecord.from_response(response))
                return response

        class _Beta:
            messages = _Messages()

        self.beta = _Beta()

    @property
    def cost_usd(self) -> Decimal:
        return sum((c.cost_usd or Decimal(0) for c in self.calls), Decimal(0))

    @property
    def unpriced_calls(self) -> int:
        return sum(1 for c in self.calls if c.cost_usd is None)
