"""Configuration file (clientsim.yaml) loading and defaults."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

DEFAULT_MIX = [
    {"intent": "asks about prices and what is included", "share": 25},
    {"intent": "wants to book, order or buy right now", "share": 15},
    {"intent": "is unsure what they need", "share": 15},
    {"intent": "negotiates or asks for a discount", "share": 10},
    {"intent": "is suspicious (is this a scam? who are you?)", "share": 8},
    {"intent": "asks for a human or a phone call", "share": 8},
    {"intent": "talks about something unrelated to the business", "share": 7},
    {"intent": "complains about a previous experience", "share": 5},
    {"intent": "asks about personal data and privacy", "share": 4},
    {"intent": "replies with STOP / wants no more messages", "share": 3},
]


@dataclass
class Target:
    kind: str                      # "anthropic" | "http" | "python"
    model: str = "claude-sonnet-5-5"
    system_prompt: str = ""
    max_tokens: int = 4000
    effort: str | None = None
    url: str = ""
    headers: dict = field(default_factory=dict)
    function: str = ""             # "package.module:function"
    handoff_marker: str = ""       # e.g. "[HANDOFF]": the bot hands the conversation to a human


@dataclass
class Config:
    business: str
    target: Target
    rules: str = ""
    language: str = "en"
    persona_mix: list = field(default_factory=lambda: list(DEFAULT_MIX))
    personas_extra: str = ""
    first_message_hint: str = ""
    max_turns: int = 6
    max_words: int = 0
    conversations: int = 50
    budget_usd: float = 5.0
    concurrency: int = 6
    simulator_model: str = "claude-opus-5-5"
    judge_model: str = "claude-opus-5-5"
    base_dir: Path = Path(".")


def load(path: str | Path) -> Config:
    path = Path(path)
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    base = path.parent
    t = dict(raw.get("target") or {})
    if "system_prompt_file" in t:
        t["system_prompt"] = (base / t.pop("system_prompt_file")).read_text(encoding="utf-8")
    target = Target(**t)
    rules = raw.get("rules", "")
    if raw.get("rules_file"):
        rules = (base / raw["rules_file"]).read_text(encoding="utf-8")
    if not raw.get("business"):
        raise ValueError("clientsim.yaml: 'business' (a short description of the business) is required")
    keys = {"language", "persona_mix", "personas_extra", "first_message_hint", "max_turns", "max_words",
            "conversations", "budget_usd", "concurrency", "simulator_model", "judge_model"}
    return Config(business=raw["business"], target=target, rules=rules, base_dir=base,
                  **{k: v for k, v in raw.items() if k in keys})
