"""Summary (Markdown) and a readable HTML report."""
from __future__ import annotations

import html
from collections import Counter


def summarize(results: list[dict]) -> dict:
    scored = [r for r in results if "verdict" in r]
    scores = [r["verdict"]["score"] for r in scored]
    issues = Counter(i["type"].strip().lower() for r in scored for i in r["verdict"]["issues"])
    critical = Counter(i["type"].strip().lower() for r in scored for i in r["verdict"]["issues"]
                       if i.get("severity") == "critical")
    incidents = Counter(i.split(" (")[0].split(":")[0] for r in results for i in r["conversation"]["incidents"])
    rules = Counter(r["verdict"]["rule_to_add"].strip() for r in scored if r["verdict"]["rule_to_add"].strip())
    return {
        "conversations": len(results),
        "average": round(sum(scores) / len(scores), 2) if scores else None,
        "distribution": dict(sorted(Counter(scores).items())),
        "silent_or_broken": sum(1 for r in results if any(i.startswith(("empty reply", "bot error"))
                                                           for i in r["conversation"]["incidents"])),
        "handoffs": sum(1 for r in results if any(t.get("handoff") for t in r["conversation"]["turns"])),
        "top_issues": issues.most_common(12),
        "critical_issues": critical.most_common(8),
        "incidents": incidents.most_common(),
        "suggested_rules": [r for r, _ in rules.most_common(15)],
    }


def markdown(s: dict, spent: float) -> str:
    lines = [f"# clientsim report", "",
             f"- Conversations: **{s['conversations']}**",
             f"- Average score: **{s['average']} / 10**",
             f"- Silent or broken bot replies: **{s['silent_or_broken']}**",
             f"- Conversations handed to a human: {s['handoffs']}",
             f"- Cost of this run: ${spent:.2f}", "",
             "## Score distribution", "", " ".join(f"{k}/10: {v}" for k, v in s["distribution"].items()), "",
             "## Most frequent issues", ""]
    lines += [f"- {t} ({n})" for t, n in s["top_issues"]] or ["- none"]
    if s["critical_issues"]:
        lines += ["", "## Critical issues", ""] + [f"- {t} ({n})" for t, n in s["critical_issues"]]
    if s["incidents"]:
        lines += ["", "## Mechanical incidents", ""] + [f"- {t} ({n})" for t, n in s["incidents"]]
    lines += ["", "## Rules the judge suggests adding to your bot", ""]
    lines += [f"- {r}" for r in s["suggested_rules"]] or ["- none"]
    return "\n".join(lines) + "\n"


def page(s: dict, results: list[dict], spent: float, worst: int = 25) -> str:
    e = html.escape
    rows = sorted((r for r in results if "verdict" in r), key=lambda r: r["verdict"]["score"])[:worst]
    convs = []
    for r in rows:
        v, c = r["verdict"], r["conversation"]
        turns = "".join(
            f"<div class='{'c' if t['who'] == 'customer' else 'b'}'>{e(t['text'])}"
            + ("<span class='h'>handed to a human</span>" if t.get("handoff") else "") + "</div>" for t in c["turns"])
        issues = "".join(f"<li><b>{e(i['type'])}</b> ({e(i['severity'])}) — {e(i['why'])}"
                         f"<br><i>“{e(i['quote'])}”</i></li>" for i in v["issues"])
        convs.append(f"<details><summary><b>{v['score']}/10</b> — {e(c['persona']['intent'])} · "
                     f"{e(c['persona']['name'])}{' · ⚠ ' + e('; '.join(c['incidents'])) if c['incidents'] else ''}"
                     f"</summary><div class='t'>{turns}</div><ul>{issues}</ul>"
                     f"<p><b>Better reply:</b> {e(v['better_reply'])}</p></details>")
    bars = "".join(f"<div><span>{k}</span><i style='width:{8 * v}px'></i>{v}</div>" for k, v in s["distribution"].items())
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>clientsim report</title><style>
:root{{--bg:#fff;--fg:#1d1d1f;--mut:#666;--c:#eef1f5;--b:#dcf8c6;--line:#ddd}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151515;--fg:#eee;--mut:#aaa;--c:#2a2d33;--b:#1f3d2a;--line:#333}}}}
body{{font:16px/1.5 system-ui;background:var(--bg);color:var(--fg);max-width:860px;margin:auto;padding:16px}}
.k{{display:flex;gap:12px;flex-wrap:wrap}}.k div{{border:1px solid var(--line);border-radius:10px;padding:10px 14px}}
.k b{{font-size:1.6em;display:block}}details{{border:1px solid var(--line);border-radius:10px;margin:10px 0;padding:8px 12px}}
.t div{{padding:6px 10px;border-radius:10px;margin:6px 0;max-width:85%;white-space:pre-wrap}}
.c{{background:var(--c)}}.b{{background:var(--b);margin-left:auto}}.h{{display:block;font-size:.8em;color:var(--mut)}}
.d div{{display:flex;align-items:center;gap:6px}}.d i{{display:inline-block;height:12px;background:#4a7}}.d span{{width:2em}}
small{{color:var(--mut)}}</style>
<h1>clientsim report</h1>
<div class="k"><div><b>{s['average']}</b>average / 10</div><div><b>{s['conversations']}</b>conversations</div>
<div><b>{s['silent_or_broken']}</b>silent or broken</div><div><b>${spent:.2f}</b>cost</div></div>
<h2>Scores</h2><div class="d">{bars}</div>
<h2>Most frequent issues</h2><ul>{''.join(f'<li>{e(t)} ({n})</li>' for t, n in s['top_issues'])}</ul>
<h2>Rules to add to your bot</h2><ul>{''.join(f'<li>{e(r)}</li>' for r in s['suggested_rules'])}</ul>
<h2>The {len(rows)} worst conversations</h2>{''.join(convs)}
<p><small>Made with clientsim — open source by JustiLoi (justiloi.com).</small></p></html>"""
