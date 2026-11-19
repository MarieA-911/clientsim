"""Persona generation, simulated customers, and the conversation loop."""
from __future__ import annotations

import json

from .config import Config
from .targets import Bot

END = "[END]"

PERSONA_SCHEMA = {
    "type": "object", "additionalProperties": False, "required": ["personas"],
    "properties": {"personas": {"type": "array", "items": {
        "type": "object", "additionalProperties": False,
        "required": ["name", "who", "intent", "style", "goal", "first_message"],
        "properties": {k: {"type": "string"} for k in ["name", "who", "intent", "style", "goal", "first_message"]}}}}}


def make_personas(cfg: Config, llm, n: int, batch: int = 25) -> list[dict]:
    mix = "\n".join(f"- {m['share']}%: {m['intent']}" for m in cfg.persona_mix)
    personas: list[dict] = []
    while len(personas) < n:
        k = min(batch, n - len(personas))
        prompt = f"""Invent {k} varied, realistic people who send a message to this business:
{cfg.business}

Intent mix (approximate shares):
{mix}
{cfg.personas_extra}
{cfg.first_message_hint}
Vary the writing styles (in a hurry, chatty, many typos, very polite, curt, elderly and unsure, young texting in
abbreviations) and the situations. "who" = a one-line description of the person. "goal" = what they want and when they
stop. "first_message" = their very first message, written exactly as they would type it.
Write everything in this language: {cfg.language}. Avoid repeating the names or situations already used: {[p['name'] for p in personas][-60:]}"""
        r = llm(model=cfg.simulator_model, messages=[{"role": "user", "content": prompt}], max_tokens=16000,
                effort="low", schema=PERSONA_SCHEMA)
        personas += json.loads(r.text)["personas"][:k]
    return personas


def customer_says(cfg: Config, llm, persona: dict, history: list[dict]) -> str:
    transcript = "\n".join(f"{'ME' if h['who'] == 'customer' else 'BUSINESS'}: {h['text']}" for h in history)
    prompt = f"""You are role-playing a customer. Stay in character.
You: {persona['who']} (name: {persona['name']}). Style: {persona['style']}.
Intent: {persona['intent']}. Goal: {persona['goal']}.
Conversation so far:
{transcript}

Write ONLY your next message, short and natural, in your own style and in {cfg.language}.
If you got what you wanted, were told a human will take over, or you give up, write exactly {END}."""
    r = llm(model=cfg.simulator_model, messages=[{"role": "user", "content": prompt}], max_tokens=2000, effort="low")
    return r.text.strip()


def converse(cfg: Config, llm, bot: Bot, persona: dict) -> dict:
    """One full conversation. Incidents are mechanical failures found without any judgement."""
    history: list[dict] = [{"who": "customer", "text": persona["first_message"]}]
    incidents: list[str] = []
    for _ in range(cfg.max_turns):
        turn = bot.reply(history, persona.get("name", ""))
        if turn.error:
            incidents.append(f"bot error: {turn.error}")
        elif not turn.text and not turn.handoff:
            incidents.append(f"empty reply (stop_reason: {turn.stop_reason or 'unknown'})")
        if turn.stop_reason == "max_tokens":
            incidents.append("reply cut by max_tokens (thinking can eat the whole budget)")
        if cfg.max_words and turn.text and len(turn.text.split()) > cfg.max_words:
            incidents.append(f"reply longer than {cfg.max_words} words ({len(turn.text.split())})")
        history.append({"who": "bot", "text": turn.text or "[NO REPLY]", "handoff": turn.handoff})
        if turn.handoff or not turn.text:
            break
        nxt = customer_says(cfg, llm, persona, history)
        if not nxt or nxt.upper().startswith(END):
            break
        history.append({"who": "customer", "text": nxt})
    return {"persona": persona, "turns": history, "incidents": incidents}
