"""Runs a batch: personas -> conversations -> verdicts -> report, with a hard budget and resumable output."""
from __future__ import annotations

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import report
from .config import Config
from .judge import judge
from .simulate import converse, make_personas
from .targets import Bot

_lock = threading.Lock()


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def run(cfg: Config, llm, out: Path, n: int, personas: list[dict] | None = None, log=print) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    pfile = out / "personas.json"
    if personas is None:
        if pfile.exists():
            personas = json.loads(pfile.read_text(encoding="utf-8"))
        else:
            log(f"Inventing {n} customers…")
            personas = make_personas(cfg, llm, n)
    pfile.write_text(json.dumps(personas, ensure_ascii=False, indent=1), encoding="utf-8")
    rfile = out / "results.jsonl"
    done = {r["index"] for r in _read_jsonl(rfile)}  # resume: never redo a finished conversation
    bot = Bot(cfg.target, llm)

    def one(i: int, persona: dict) -> None:
        if i in done or llm.ledger.exhausted:
            return
        try:
            conv = converse(cfg, llm, bot, persona)
            verdict = judge(cfg, llm, conv)
        except Exception as e:  # noqa: BLE001
            log(f"#{i:<3} failed: {type(e).__name__}: {str(e)[:160]}")
            return
        with _lock, rfile.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"index": i, "conversation": conv, "verdict": verdict}, ensure_ascii=False) + "\n")
        flag = f"  ⚠ {conv['incidents'][0]}" if conv["incidents"] else ""
        log(f"#{i:<3} {verdict['score']:>2}/10  ${llm.ledger.spent:6.2f}  {persona['intent'][:50]}{flag}")

    with ThreadPoolExecutor(cfg.concurrency) as ex:
        list(ex.map(lambda a: one(*a), enumerate(personas)))
    if llm.ledger.exhausted:
        log(f"Budget of ${llm.ledger.budget:.2f} reached: stopped early (run again to resume).")
    return write_report(out, llm.ledger.spent)


def write_report(out: Path, spent: float = 0.0) -> dict:
    results = _read_jsonl(out / "results.jsonl")
    meta = out / "cost.json"
    total = spent + (json.loads(meta.read_text())["usd"] if meta.exists() else 0.0)
    meta.write_text(json.dumps({"usd": round(total, 4)}))
    s = report.summarize(results)
    (out / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "report.md").write_text(report.markdown(s, total), encoding="utf-8")
    (out / "report.html").write_text(report.page(s, results, total), encoding="utf-8")
    return s


def rejudge(cfg: Config, llm, out: Path, log=print) -> dict:
    """Score existing conversations again (after changing the rules or the judge), without re-running the bot."""
    results = _read_jsonl(out / "results.jsonl")

    def one(r):
        if llm.ledger.exhausted:
            return r
        r["verdict"] = judge(cfg, llm, r["conversation"])
        log(f"#{r['index']:<3} {r['verdict']['score']:>2}/10")
        return r

    with ThreadPoolExecutor(cfg.concurrency) as ex:
        results = list(ex.map(one, results))
    (out / "results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results),
                                       encoding="utf-8")
    return write_report(out, llm.ledger.spent)


def worst_personas(run_dir: Path, k: int) -> tuple[list[dict], list[int]]:
    rows = sorted(_read_jsonl(run_dir / "results.jsonl"), key=lambda r: r["verdict"]["score"])[:k]
    return [r["conversation"]["persona"] for r in rows], [r["verdict"]["score"] for r in rows]
