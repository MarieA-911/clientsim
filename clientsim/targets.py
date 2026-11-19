"""The bot under test. Three ways to plug it in: a Claude system prompt, an HTTP endpoint, or a Python function."""
from __future__ import annotations

import importlib
import json
import urllib.request
from dataclasses import dataclass

from .config import Target
from .llm import Reply


@dataclass
class BotTurn:
    text: str
    handoff: bool = False
    stop_reason: str = ""
    error: str = ""


def _as_messages(history: list[dict]) -> list[dict]:
    """history items: {"who": "customer"|"bot", "text": ...} -> alternating user/assistant messages."""
    out: list[dict] = []
    for h in history:
        role = "user" if h["who"] == "customer" else "assistant"
        if out and out[-1]["role"] == role:
            out[-1]["content"] += "\n" + h["text"]
        else:
            out.append({"role": role, "content": h["text"]})
    return out


def _split_handoff(text: str, marker: str) -> tuple[str, bool]:
    if marker and marker in text:
        return text.replace(marker, "").strip(), True
    return text.strip(), False


class Bot:
    def __init__(self, target: Target, llm=None):
        self.t = target
        self.llm = llm
        self._fn = None
        if target.kind == "python":
            mod, _, name = target.function.partition(":")
            self._fn = getattr(importlib.import_module(mod), name)
        elif target.kind not in ("anthropic", "http"):
            raise ValueError(f"unknown target kind: {target.kind}")

    def reply(self, history: list[dict], persona_name: str = "") -> BotTurn:
        try:
            if self.t.kind == "anthropic":
                r: Reply = self.llm(model=self.t.model, system=self.t.system_prompt, messages=_as_messages(history),
                                    max_tokens=self.t.max_tokens, effort=self.t.effort)
                text, handoff = _split_handoff(r.text, self.t.handoff_marker)
                return BotTurn(text, handoff, r.stop_reason)
            if self.t.kind == "http":
                body = json.dumps({"messages": _as_messages(history), "customer_name": persona_name}).encode()
                req = urllib.request.Request(self.t.url, data=body, method="POST",
                                             headers={"Content-Type": "application/json", **self.t.headers})
                with urllib.request.urlopen(req, timeout=90) as resp:
                    data = json.loads(resp.read() or b"{}")
                text, handoff = _split_handoff(str(data.get("reply", "")), self.t.handoff_marker)
                return BotTurn(text, handoff or bool(data.get("handoff")), "http")
            out = self._fn(_as_messages(history))
            if isinstance(out, dict):
                text, handoff = _split_handoff(str(out.get("reply", "")), self.t.handoff_marker)
                return BotTurn(text, handoff or bool(out.get("handoff")), "python")
            text, handoff = _split_handoff(str(out or ""), self.t.handoff_marker)
            return BotTurn(text, handoff, "python")
        except Exception as e:  # noqa: BLE001 - every failure of the bot is a finding, not a crash
            return BotTurn("", False, "error", f"{type(e).__name__}: {str(e)[:200]}")
