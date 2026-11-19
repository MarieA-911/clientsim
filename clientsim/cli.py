"""Command line: clientsim run | replay | rejudge | report | init."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import load
from .llm import LLM, Ledger
from .runner import rejudge, run, worst_personas, write_report

TEMPLATE = """# clientsim.yaml — test your chatbot against simulated customers.
business: >
  Describe the business in two or three sentences: what it sells, prices, opening hours, where it is,
  and how customers usually reach it (WhatsApp, website chat, Messenger...).

target:
  kind: anthropic              # anthropic | http | python
  model: claude-sonnet-5-5
  system_prompt_file: bot_prompt.md
  max_tokens: 4000
  effort: low
  handoff_marker: "[HANDOFF]"  # optional: what your bot writes when a human must take over
  # kind: http  ->  url: https://example.com/bot   (POST {"messages": [...]} -> {"reply": "...", "handoff": false})
  # kind: python -> function: mybot.module:reply  (reply(messages) -> str or {"reply": ..., "handoff": ...})

# rules_file: rules.md         # what the bot must / must not do (defaults to the bot's system prompt)
language: en                   # language of customers and of the report
max_words: 80                  # flag replies longer than this (0 = no limit)
max_turns: 6
conversations: 50
budget_usd: 5
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="clientsim", description="Test your AI chatbot against simulated customers.")
    p.add_argument("--version", action="version", version=f"clientsim {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="write a starter clientsim.yaml in the current folder")
    r = sub.add_parser("run", help="simulate conversations, judge them, write a report")
    r.add_argument("-c", "--config", default="clientsim.yaml")
    r.add_argument("-n", "--conversations", type=int)
    r.add_argument("--budget", type=float, help="hard spending limit in USD for this run")
    r.add_argument("-o", "--out", help="output folder (default: runs/<date-time>); reuse it to resume")
    rp = sub.add_parser("replay", help="re-run the worst personas of a previous run against the current bot")
    rp.add_argument("run_dir")
    rp.add_argument("-c", "--config", default="clientsim.yaml")
    rp.add_argument("--worst", type=int, default=10)
    rp.add_argument("--budget", type=float)
    rj = sub.add_parser("rejudge", help="score the conversations of a run again (new rules or judge)")
    rj.add_argument("run_dir")
    rj.add_argument("-c", "--config", default="clientsim.yaml")
    rj.add_argument("--budget", type=float)
    rr = sub.add_parser("report", help="rebuild report.md / report.html of a run")
    rr.add_argument("run_dir")
    a = p.parse_args(argv)

    if a.cmd == "init":
        f = Path("clientsim.yaml")
        if f.exists():
            print("clientsim.yaml already exists.")
            return 1
        f.write_text(TEMPLATE, encoding="utf-8")
        Path("bot_prompt.md").exists() or Path("bot_prompt.md").write_text("You are the assistant of ...\n",
                                                                         encoding="utf-8")
        print("Wrote clientsim.yaml and bot_prompt.md — edit them, set ANTHROPIC_API_KEY, then: clientsim run")
        return 0
    if a.cmd == "report":
        s = write_report(Path(a.run_dir))
        print(f"Average {s['average']}/10 over {s['conversations']} conversations — {a.run_dir}/report.html")
        return 0

    cfg = load(a.config)
    ledger = Ledger(budget=a.budget if a.budget is not None else cfg.budget_usd)
    llm = LLM(ledger)
    if a.cmd == "run":
        out = Path(a.out or f"runs/{datetime.now():%Y-%m-%d_%H%M}")
        s = run(cfg, llm, out, a.conversations or cfg.conversations)
    elif a.cmd == "rejudge":
        out = Path(a.run_dir)
        s = rejudge(cfg, llm, out)
    else:
        personas, before = worst_personas(Path(a.run_dir), a.worst)
        out = Path(a.run_dir) / f"replay-{datetime.now():%Y-%m-%d_%H%M}"
        s = run(cfg, llm, out, len(personas), personas=personas)
        print(f"\nSame {len(personas)} customers — before: {sum(before) / len(before):.1f}/10, "
              f"now: {s['average']}/10")
    print(f"\nAverage {s['average']}/10 · {s['silent_or_broken']} silent/broken · ${ledger.spent:.2f} spent")
    print(f"Report: {out / 'report.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
