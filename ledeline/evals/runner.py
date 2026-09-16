"""Run the workflow for every (model, source) pair, check + judge each output, write one
results file, and compare against the last accepted baseline.

    python -m ledeline.evals.runner --models gemini:gemini-2.5-flash-lite gemini:gemini-2.5-flash \
        --judge gemini:gemini-2.5-flash --out results/run.json

The ship gate is deliberately boring: a model config ships only if (a) it passes at least as
many deterministic checks as the baseline on every source and (b) its mean judge score does
not drop by more than `--tolerance`. "Better on average" is not enough if it started inventing
numbers on one story; that is what the per-source comparison is for.
"""
from __future__ import annotations
import argparse, json, statistics, sys, time
from pathlib import Path
from .. import providers, workflow
from . import checks, judge

ROOT = Path(__file__).resolve().parent.parent.parent


def load_corpus():
    meta = json.loads((ROOT / "corpus" / "sources.json").read_text())
    out = []
    for m in meta:
        g = ROOT / "corpus" / "golden" / f"{m['id']}.json"
        golden = json.loads(g.read_text()) if g.exists() else {"must_mention": []}
        out.append({**m, "text": (ROOT / "corpus" / "sources" / f"{m['id']}.txt").read_text(), "golden": golden})
    return out


def run_one(model_spec: str, src: dict, spec: str, judge_provider) -> dict:
    prov = providers.make(model_spec)
    row = {"model": model_spec, "source": src["id"], "title": src["title"]}
    try:
        blurb, comp = workflow.run(prov, src["title"], src["url"], src["text"], spec)
    except Exception as e:
        row.update({"error": str(e)[:300], "checks": {"passed": False, "findings": []}, "judge": None})
        return row
    ck = checks.check(blurb.headline, blurb.blurb, blurb.claims, src["text"])
    row.update({"headline": blurb.headline, "blurb": blurb.blurb, "claims": blurb.claims,
                "latency_ms": comp.latency_ms, "input_tokens": comp.input_tokens, "output_tokens": comp.output_tokens,
                "checks": ck.to_dict()})
    try:
        row["judge"] = judge.grade(judge_provider, spec, src["title"], src["text"], src["golden"].get("must_mention", []),
                                   blurb.headline, blurb.blurb)
    except Exception as e:
        row["judge"] = None; row["judge_error"] = str(e)[:300]
    return row


def summarize(rows: list[dict]) -> dict:
    by = {}
    for r in rows:
        by.setdefault(r["model"], []).append(r)
    out = {}
    for m, rs in by.items():
        ok = [r for r in rs if r.get("checks", {}).get("passed")]
        judged = [r["judge"]["total"] for r in rs if r.get("judge")]
        rule_fail = {}
        for r in rs:
            for f in r.get("checks", {}).get("findings", []):
                if not f["ok"]:
                    rule_fail[f["rule"]] = rule_fail.get(f["rule"], 0) + 1
        out[m] = {"n": len(rs), "errors": sum(1 for r in rs if r.get("error")),
                  "checks_pass_rate": round(len(ok) / len(rs), 3) if rs else 0,
                  "judge_mean": round(statistics.mean(judged), 2) if judged else None,
                  "judge_max": 8, "rule_failures": rule_fail,
                  "p50_latency_ms": int(statistics.median([r["latency_ms"] for r in rs if "latency_ms" in r])) if any("latency_ms" in r for r in rs) else None}
    return out


def ship_gate(candidate: str, baseline: str, rows: list[dict], tolerance: float = 0.5) -> dict:
    """Per-source comparison. A candidate ships only if it never loses a deterministic check the
    baseline passed on the same story and its judge mean does not fall by more than tolerance."""
    cand = {r["source"]: r for r in rows if r["model"] == candidate}
    base = {r["source"]: r for r in rows if r["model"] == baseline}
    regressions = []
    for sid, b in base.items():
        c = cand.get(sid)
        if not c:
            continue
        b_fail = set(f["rule"] for f in b["checks"]["findings"] if not f["ok"])
        c_fail = set(f["rule"] for f in c["checks"]["findings"] if not f["ok"])
        new_fail = c_fail - b_fail
        if new_fail or c.get("error"):
            regressions.append({"source": sid, "new_failures": sorted(new_fail), "error": c.get("error")})
    def mean(d):
        v = [r["judge"]["total"] for r in d.values() if r.get("judge")]
        return statistics.mean(v) if v else None
    bm, cm = mean(base), mean(cand)
    judge_ok = bm is None or cm is None or (bm - cm) <= tolerance
    return {"candidate": candidate, "baseline": baseline, "ships": not regressions and judge_ok,
            "regressions": regressions, "judge_mean_baseline": bm, "judge_mean_candidate": cm, "tolerance": tolerance}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--judge", default="gemini:gemini-2.5-flash")
    ap.add_argument("--baseline", help="model spec treated as the currently shipped config")
    ap.add_argument("--out", default=str(ROOT / "results" / f"run-{time.strftime('%Y%m%d-%H%M%S')}.json"))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between calls (free-tier rate limits)")
    a = ap.parse_args()
    spec = workflow.load_spec()
    corpus = load_corpus()
    if a.limit:
        corpus = corpus[: a.limit]
    jp = providers.make(a.judge)
    rows = []
    for m in a.models:
        for src in corpus:
            print(f"  {m:32} {src['id'][:40]:40}", end=" ", flush=True)
            r = run_one(m, src, spec, jp)
            rows.append(r)
            print("ERR" if r.get("error") else ("pass" if r["checks"]["passed"] else "FAIL " + ",".join(r["checks"] and [f["rule"] for f in r["checks"]["findings"] if not f["ok"]])),
                  "judge", r["judge"]["total"] if r.get("judge") else "-", flush=True)
            time.sleep(a.sleep)
    summary = summarize(rows)
    gates = []
    if a.baseline:
        for m in a.models:
            if m != a.baseline:
                gates.append(ship_gate(m, a.baseline, rows))
    out = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"), "spec_sha": __import__("hashlib").sha256(spec.encode()).hexdigest()[:12],
           "judge": a.judge, "models": a.models, "baseline": a.baseline, "summary": summary, "gates": gates, "rows": rows}
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({"summary": summary, "gates": gates}, indent=1))
    print("->", a.out)


if __name__ == "__main__":
    main()
