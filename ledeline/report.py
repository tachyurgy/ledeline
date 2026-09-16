"""results/*.json -> site/index.html. One static page, no build step, no JS framework.
    python -m ledeline.report results/run-2026-09-15.json site/index.html
"""
from __future__ import annotations
import html, json, sys
from pathlib import Path

CSS = """
:root{--bg:#0f1115;--card:#171a21;--ink:#e8e6e1;--mut:#9a9890;--ok:#5fbf7a;--bad:#e06c6c;--acc:#f2b84b;--line:#262a33}
@media (prefers-color-scheme: light){:root{--bg:#f7f6f2;--card:#fff;--ink:#1b1b1b;--mut:#666;--line:#e3e1da}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 "Inter Tight",system-ui,-apple-system,Segoe UI,sans-serif}
main{max-width:1040px;margin:0 auto;padding:32px 16px 80px}h1{font-size:30px;margin:0 0 4px;letter-spacing:-.01em}
h2{font-size:18px;margin:36px 0 10px}.sub{color:var(--mut);margin:0 0 24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.k{font-size:12px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em}.v{font-size:26px;font-weight:700;margin-top:2px}
.ok{color:var(--ok)}.bad{color:var(--bad)}.acc{color:var(--acc)}
table{width:100%;border-collapse:collapse;font-size:14px}th,td{text-align:left;padding:8px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:.05em}
code,pre{font-family:"JetBrains Mono",ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
pre{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;overflow:auto;white-space:pre-wrap}
details{border:1px solid var(--line);border-radius:10px;background:var(--card);margin:10px 0;padding:10px 14px}
summary{cursor:pointer;font-weight:600}.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:12px;border:1px solid var(--line);margin:2px 4px 2px 0}
.blurb{margin:8px 0;padding:10px 12px;border-left:3px solid var(--line)}.blurb.pass{border-color:var(--ok)}.blurb.fail{border-color:var(--bad)}
.small{color:var(--mut);font-size:13px}a{color:var(--acc)}
"""


def esc(s):
    return html.escape(str(s if s is not None else ""))


def render(run: dict) -> str:
    models = run["models"]; summ = run["summary"]; gates = run.get("gates", [])
    parts = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
             f"<title>Ledeline eval run</title><style>{CSS}</style></head><body><main>"
             f"<h1>Ledeline</h1><p class=sub>Spec-driven newsletter blurbs. The spec is the prompt, the evals read the spec, and a model change ships only if the evals say so. "
             f"Run {esc(run['run_at'])} · spec <code>{esc(run['spec_sha'])}</code> · judge <code>{esc(run['judge'])}</code> · {len(run['rows'])} generations</p>"]
    parts.append("<div class=grid>")
    for m in models:
        s = summ[m]
        cls = "ok" if s["checks_pass_rate"] == 1 else ("acc" if s["checks_pass_rate"] >= 0.8 else "bad")
        parts.append(f"<div class=card><div class=k>{esc(m)}{' · baseline' if m == run.get('baseline') else ''}</div>"
                     f"<div class='v {cls}'>{int(s['checks_pass_rate']*100)}% checks</div>"
                     f"<div class=small>judge {s['judge_mean']} / {s['judge_max']} · p50 {s['p50_latency_ms']} ms · {s['errors']} errors</div>"
                     + ("".join(f"<span class=pill>{esc(k)} ×{v}</span>" for k, v in s['rule_failures'].items()) or "<div class=small>no rule failures</div>") + "</div>")
    parts.append("</div>")
    if gates:
        parts.append("<h2>Ship gate</h2>")
        for g in gates:
            verdict = "<span class=ok>SHIPS</span>" if g["ships"] else "<span class=bad>DOES NOT SHIP</span>"
            parts.append(f"<div class=card><b>{esc(g['candidate'])}</b> vs baseline <b>{esc(g['baseline'])}</b>: {verdict}"
                         f"<div class=small>judge mean {g['judge_mean_candidate']} vs {g['judge_mean_baseline']} (tolerance {g['tolerance']}); "
                         f"{len(g['regressions'])} per-story regressions</div>")
            for r in g["regressions"]:
                parts.append(f"<div class=small>· {esc(r['source'])}: new failures {esc(', '.join(r['new_failures']))} {esc(r.get('error') or '')}</div>")
            parts.append("</div>")
    parts.append("<h2>Per story</h2><p class=small>Every generation, its deterministic findings and the judge's reasons. Nothing is hidden behind an average.</p>")
    srcs = []
    for r in run["rows"]:
        if r["source"] not in srcs:
            srcs.append(r["source"])
    for sid in srcs:
        rows = [r for r in run["rows"] if r["source"] == sid]
        parts.append(f"<details><summary>{esc(rows[0]['title'])}</summary>")
        for r in rows:
            ok = r.get("checks", {}).get("passed")
            parts.append(f"<div class='blurb {'pass' if ok else 'fail'}'><div class=small><code>{esc(r['model'])}</code> · "
                         f"{'pass' if ok else 'FAIL'} · judge {r['judge']['total'] if r.get('judge') else '-'}/8 · {r.get('latency_ms','-')} ms</div>")
            if r.get("error"):
                parts.append(f"<div class=bad>{esc(r['error'])}</div></div>"); continue
            parts.append(f"<div><b>{esc(r['headline'])}</b></div><div>{esc(r['blurb'])}</div>")
            fails = [f for f in r["checks"]["findings"] if not f["ok"]]
            if fails:
                parts.append("<div class=small>" + " ".join(f"<span class='pill bad'>{esc(f['rule'])}: {esc(f['detail'])}</span>" for f in fails) + "</div>")
            if r.get("judge"):
                j = r["judge"]
                parts.append("<div class=small>" + " ".join(f"<span class=pill>{esc(k)} {v}</span>" for k, v in j["scores"].items()) + "</div>")
                low = [f"<b>{esc(k)}</b>: {esc(j['reasons'][k])}" for k, v in j["scores"].items() if v < 2]
                if low:
                    parts.append("<div class=small>" + "<br>".join(low) + "</div>")
            parts.append("</div>")
        parts.append("</details>")
    parts.append("<h2>How to read this</h2><pre>" + esc(HOW) + "</pre>")
    parts.append("<p class=small>Source: <a href='https://github.com/tachyurgy/ledeline'>github.com/tachyurgy/ledeline</a></p></main></body></html>")
    return "".join(parts)


HOW = """Deterministic checks map one-to-one to numbered rules in specs/blurb.md. They cost zero tokens and
run in the test suite. The two that matter are rule1.numbers_grounded and rule1.names_grounded: a
number, year, price or capitalised name that is not in the source fails the story, full stop.

The judge is a separate, fixed model that never grades its own output. It scores four criteria
0-2 with a reason each, against must-mention notes a human editor wrote per story.

The ship gate compares a candidate model config to the baseline PER STORY. Better on average does
not ship if it introduced a new deterministic failure on any single story."""


def main():
    src, out = Path(sys.argv[1]), Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(json.loads(src.read_text())))
    print("->", out)


if __name__ == "__main__":
    main()
