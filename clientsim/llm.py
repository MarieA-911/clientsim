"""Thin wrapper around the Anthropic SDK, with cost tracking and a fake for tests."""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field

# USD per million tokens (input, output). Override in the config if prices change.
PRICES = {
    "claude-opus-5-5": (4.0, 20.0),
    "claude-sonnet-5-5": (2.0, 10.0),
    "claude-haiku-5-5": (0.10, 0.50),
}
WEB_SEARCH_PRICE = 0.01


@dataclass
class Reply:
    text: str
    stop_reason: str
    cost: float = 0.0


@dataclass
class Ledger:
    """Running total of what a run has spent, with a hard budget."""
    budget: float
    spent: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def add(self, amount: float) -> None:
        with self._lock:
            self.spent += amount

    @property
    def exhausted(self) -> bool:
        return self.spent >= self.budget


def cost_of(model: str, usage, prices: dict | None = None) -> float:
    pin, pout = (prices or PRICES).get(model, PRICES["claude-opus-5-5"])
    inp = (getattr(usage, "input_tokens", 0) or 0)
    inp += (getattr(usage, "cache_creation_input_tokens", 0) or 0) * 1.25
    inp += (getattr(usage, "cache_read_input_tokens", 0) or 0) * 0.1
    total = inp * pin / 1e6 + (getattr(usage, "output_tokens", 0) or 0) * pout / 1e6
    stu = getattr(usage, "server_tool_use", None)
    if stu is not None:
        total += (getattr(stu, "web_search_requests", 0) or 0) * WEB_SEARCH_PRICE
    return total


class LLM:
    """Calls Claude. `schema` asks for JSON matching a JSON Schema (structured outputs)."""

    def __init__(self, ledger: Ledger, api_key: str | None = None, prices: dict | None = None):
        import anthropic  # imported here so the tests run without the SDK

        self.client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"), max_retries=4)
        self.ledger = ledger
        self.prices = prices

    def __call__(self, *, model: str, messages: list[dict], system: str | None = None, max_tokens: int = 4000,
                 effort: str | None = None, schema: dict | None = None) -> Reply:
        kwargs: dict = {"model": model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system
        output_config: dict = {}
        if effort:
            output_config["effort"] = effort
        if schema:
            output_config["format"] = {"type": "json_schema", "schema": schema}
        if output_config:
            kwargs["output_config"] = output_config
        resp = self.client.messages.create(**kwargs)
        cost = cost_of(model, resp.usage, self.prices)
        self.ledger.add(cost)
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return Reply(text=text, stop_reason=resp.stop_reason or "", cost=cost)


class FakeLLM:
    """Deterministic stand-in for tests: `script(model, messages, system, schema)` returns the text."""

    def __init__(self, script, ledger: Ledger | None = None):
        self.script = script
        self.ledger = ledger or Ledger(budget=1e9)
        self.calls: list[dict] = []

    def __call__(self, *, model, messages, system=None, max_tokens=4000, effort=None, schema=None) -> Reply:
        self.calls.append({"model": model, "messages": messages, "system": system, "schema": schema})
        out = self.script(model=model, messages=messages, system=system, schema=schema)
        if isinstance(out, Reply):
            return out
        return Reply(text=out if isinstance(out, str) else json.dumps(out), stop_reason="end_turn", cost=0.001)
