"""LLM-as-judge for the things a regex cannot see: is the blurb faithful to the source in
meaning, does it lead with what matters, would an editor ship it. The judge gets the source,
the spec and the golden notes (must-mention facts written by a human) and returns a rubric.

Two design choices that matter:
- The judge model is fixed per run and is NOT the model under test, so a candidate model
  cannot grade itself.
- Scores are per-criterion integers 0-2 with a one-line reason each, never a single vibe score,
  so a regression report can say WHICH criterion moved.
"""
from __future__ import annotations
import json, re

RUBRIC = ["faithful", "leads_with_substance", "covers_must_mention", "shippable"]

SYSTEM = """You are a strict newsletter editor grading a blurb against its source article and a spec.
Score each criterion 0, 1 or 2:
- faithful: 2 = every statement is supported by the source; 1 = a minor stretch; 0 = a claim the source does not support.
- leads_with_substance: 2 = first sentence says what happened and why it matters; 1 = buried; 0 = describes the article instead of the thing.
- covers_must_mention: 2 = all must-mention facts present; 1 = some; 0 = none.
- shippable: 2 = you would publish it unchanged; 1 = one edit; 0 = rewrite.
Return JSON: {"scores": {"faithful": n, "leads_with_substance": n, "covers_must_mention": n, "shippable": n}, "reasons": {same keys: one sentence each}}"""


def grade(judge_provider, spec: str, source_title: str, source_text: str, must_mention: list[str],
          headline: str, blurb: str) -> dict:
    user = (f"SPEC:\n{spec}\n\nSOURCE TITLE: {source_title}\nSOURCE TEXT:\n{source_text[:12000]}\n\n"
            f"MUST-MENTION FACTS (written by a human editor):\n- " + "\n- ".join(must_mention) +
            f"\n\nCANDIDATE HEADLINE: {headline}\nCANDIDATE BLURB: {blurb}\n\nGrade it.")
    comp = judge_provider.complete(SYSTEM, user, json_mode=True, temperature=0.0)
    m = re.search(r"\{.*\}", comp.text, re.S)
    obj = json.loads(m.group(0)) if m else {}
    scores = {k: int(obj.get("scores", {}).get(k, 0)) for k in RUBRIC}
    reasons = {k: str(obj.get("reasons", {}).get(k, "")) for k in RUBRIC}
    return {"scores": scores, "reasons": reasons, "total": sum(scores.values()), "max": 2 * len(RUBRIC),
            "judge_model": comp.model, "latency_ms": comp.latency_ms}
