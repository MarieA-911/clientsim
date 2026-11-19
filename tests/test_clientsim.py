"""Offline tests: a fake LLM plays the simulator, the bot and the judge."""
import json
from pathlib import Path

import pytest

from clientsim import cli
from clientsim.config import Config, Target, load
from clientsim.judge import transcript
from clientsim.llm import FakeLLM, Ledger, Reply
from clientsim.runner import run, worst_personas
from clientsim.simulate import converse
from clientsim.targets import Bot

PERSONA = {"name": "Rose", "who": "hairdresser in Pointe-à-Pitre", "intent": "asks the price", "style": "short",
           "goal": "get the price", "first_message": "hello how much?"}


def script(bot_text="Hello Rose! It is 20 €. Anything else?", customer_lines=("thanks", "[END]")):
    lines = iter(customer_lines)

    def s(model, messages, system=None, schema=None):
        prompt = messages[-1]["content"]
        if schema and "personas" in schema["properties"]:
            return {"personas": [dict(PERSONA, name=f"P{i}") for i in range(30)]}
        if schema:  # judge
            return {"score": 3 if "[NO REPLY]" in prompt else 8, "issues": [], "better_reply": "", "rule_to_add": ""}
        if system is not None:  # the bot under test has a system prompt
            return bot_text
        return next(lines, "[END]")
    return s


def cfg(**kw):
    return Config(business="A hair salon", target=Target(kind="anthropic", system_prompt="Be nice",
                                                          handoff_marker="[HANDOFF]"), **kw)


def test_conversation_ends_on_end_marker():
    llm = FakeLLM(script())
    conv = converse(cfg(), llm, Bot(cfg().target, llm), PERSONA)
    assert [t["who"] for t in conv["turns"]] == ["customer", "bot", "customer", "bot"]
    assert conv["incidents"] == []


def test_silent_bot_is_an_incident_and_caps_the_score(tmp_path):
    def silent(model, messages, system=None, schema=None):
        if system is not None:
            return Reply(text="", stop_reason="max_tokens")
        return script()(model, messages, system, schema)
    llm = FakeLLM(silent)
    s = run(cfg(), llm, tmp_path, 3, personas=[PERSONA] * 3, log=lambda *_: None)
    assert s["silent_or_broken"] == 3 and s["average"] <= 2
    assert any("max_tokens" in i[0] for i in s["incidents"])


def test_handoff_marker_is_hidden_from_customer_but_shown_to_judge():
    llm = FakeLLM(script(bot_text="Marie will call you back. [HANDOFF]"))
    conv = converse(cfg(), llm, Bot(cfg().target, llm), PERSONA)
    assert conv["turns"][-1]["handoff"] is True and "[HANDOFF]" not in conv["turns"][-1]["text"]
    assert "[HANDOFF] emitted" in transcript(conv, "[HANDOFF]")


def test_long_replies_are_flagged():
    llm = FakeLLM(script(bot_text="word " * 120))
    conv = converse(cfg(max_words=80), llm, Bot(cfg().target, llm), PERSONA)
    assert any("longer than 80 words" in i for i in conv["incidents"])


def test_python_target_and_bot_errors(tmp_path, monkeypatch):
    mod = tmp_path / "mybot.py"
    mod.write_text("def reply(messages):\n    raise RuntimeError('db down')\n")
    monkeypatch.syspath_prepend(str(tmp_path))
    llm = FakeLLM(script())
    bot = Bot(Target(kind="python", function="mybot:reply"), llm)
    conv = converse(cfg(), llm, bot, PERSONA)
    assert conv["incidents"] and conv["incidents"][0].startswith("bot error: RuntimeError")


def test_run_resumes_and_respects_budget(tmp_path):
    llm = FakeLLM(script(), Ledger(budget=0.0))  # budget already exhausted: nothing runs
    s = run(cfg(), llm, tmp_path, 5, log=lambda *_: None)
    assert s["conversations"] == 0
    llm = FakeLLM(script())
    run(cfg(), llm, tmp_path, 5, log=lambda *_: None)
    calls = len(llm.calls)
    run(cfg(), llm, tmp_path, 5, log=lambda *_: None)  # second run: everything already done
    assert len(llm.calls) == calls
    assert len(json.loads((tmp_path / "personas.json").read_text(encoding="utf-8"))) == 5
    assert (tmp_path / "report.html").exists() and "clientsim report" in (tmp_path / "report.md").read_text("utf-8")
    personas, scores = worst_personas(tmp_path, 2)
    assert len(personas) == 2 and scores == [8, 8]


def test_config_loading_and_init(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert cli.main(["init"]) == 0
    c = load(tmp_path / "clientsim.yaml")
    assert c.target.kind == "anthropic" and c.target.system_prompt.startswith("You are")
    (tmp_path / "bad.yaml").write_text("target: {kind: http}\n")
    with pytest.raises(ValueError):
        load(tmp_path / "bad.yaml")


def test_examples_are_valid():
    for f in Path(__file__).resolve().parents[1].glob("examples/*/clientsim.yaml"):
        c = load(f)
        assert c.business and c.target.system_prompt
