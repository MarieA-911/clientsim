"""The judge: scores each conversation against the business rules and explains every issue."""
from __future__ import annotations

import json

from .config import Config

CATEGORIES = ["invented_information", "unkept_promise", "wrong_offer", "too_long", "several_questions", "unnecessary_question",
              "missed_handoff", "useless_handoff", "tone", "silence", "ignored_question", "wrong_language",
              "unsafe_request", "stop_not_respected", "incomplete_answer", "other"]

JUDGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["score", "issues", "better_reply", "rule_to_add"],
    "properties": {
        "score": {"type": "integer"},
        "issues": {"type": "array", "items": {
            "type": "object", "additionalProperties": False, "required": ["type", "severity", "quote", "why"],
            "properties": {"type": {"type": "string", "enum": CATEGORIES},
                           "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
                           "quote": {"type": "string"}, "why": {"type": "string"}}}},
        "better_reply": {"type": "string"},
        "rule_to_add": {"type": "string"}}}

CHECKLIST = """Check in particular: invented prices, products, dates or services; promises the business cannot keep;
the wrong offer for what the customer asked; replies too long for a chat; several questions in one message;
missed handoff (a human was needed but the bot kept going) or useless handoff; wrong tone; silence or empty reply;
ignoring what the customer said; answering in another language than the customer's; asking for passwords or card
numbers; not respecting STOP."""


def transcript(conv: dict, marker: str) -> str:
    lines = []
    for t in conv["turns"]:
        who = "CUSTOMER" if t["who"] == "customer" else "BOT"
        lines.append(f"{who}: {t['text']}")
        if t.get("handoff"):
            # The marker is removed from what the customer sees; the judge must still know it was emitted.
            lines.append(f"   ({marker or 'handoff'} emitted: the conversation is handed to a human, who is alerted)")
    return "\n".join(lines)


def judge(cfg: Config, llm, conv: dict) -> dict:
    prompt = f"""You review the quality of a customer-facing chatbot for this business:
{cfg.business}

The bot's rules (what it must and must not do):
<rules>
{cfg.rules or cfg.target.system_prompt or '(no rules given: judge against common sense for this business)'}
</rules>

Simulated customer profile: {json.dumps(conv['persona'], ensure_ascii=False)}
Mechanical incidents already detected: {conv['incidents'] or 'none'}

Conversation:
{transcript(conv, cfg.target.handoff_marker)}

Score the bot from 0 to 10 (10 = a great human employee would not have done better). {CHECKLIST}
List every issue with a short quote; "type" is the closest category and "why" explains it precisely. "better_reply" = the ideal reply at the worst moment. "rule_to_add" = one
sentence to add to the bot's instructions to prevent the main issue (empty if none).
Write in {cfg.language}."""
    r = llm(model=cfg.judge_model, messages=[{"role": "user", "content": prompt}], max_tokens=8000,
            effort="medium", schema=JUDGE_SCHEMA)
    out = json.loads(r.text)
    out["score"] = max(0, min(10, int(out["score"])))
    if conv["incidents"] and any(i.startswith(("empty reply", "bot error")) for i in conv["incidents"]):
        out["score"] = min(out["score"], 2)  # a silent bot loses the customer, whatever else happened
    return out
