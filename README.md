# Ledeline

Spec-driven newsletter blurbs, with the evals that decide whether a model change ships.

The idea under test: a workflow should get better on its own as models get better, and the
people around it should be writing **specs and evals** rather than re-prompting by hand. So
this repo has no prompt strings in code. `specs/blurb.md` is the contract an editor writes;
the workflow feeds it to the model, the deterministic checks enforce its numbered rules, an
LLM judge grades what regexes cannot see, and a ship gate compares any candidate model
config against the current baseline **per story** before it is allowed to replace it.

Live report from the committed run: **https://ledeline.levelbrook.com**

## What is in here

```
specs/blurb.md            the spec. The prompt IS this file. Rules are numbered.
ledeline/workflow.py      source article -> spec -> model -> {headline, blurb, claims}
ledeline/providers.py     one call signature over Gemini / Anthropic / OpenAI REST; "gemini:gemini-2.5-flash" is a whole model config
ledeline/evals/checks.py  deterministic checks, one per spec rule, zero tokens (tests/ covers these)
ledeline/evals/judge.py   LLM-as-judge, fixed model, four 0-2 criteria with reasons, never grades its own output
ledeline/evals/runner.py  model x story matrix -> results/*.json; ship gate vs baseline
ledeline/report.py        results -> one static HTML page
corpus/sources/           ten articles from the Hacker News front page on 2026-09-15 (text only)
corpus/golden/            per-story must-mention notes, written by hand
results/                  committed runs
```

## The correctness property

Rule 1 of the spec says every fact must come from the source. `checks.py` enforces the part of
that a program can enforce: **every number, year, price, percentage and capitalised name in the
blurb must appear in the source text.** It is a proxy, not a proof; it will not catch a wrong verb
between two real names, which is what the judge is for. But it catches the failure that
actually costs a newsletter its credibility, a company or a figure that was never in the
article, at zero tokens, and it runs in the test suite:

```
python -m pytest -q tests
```

## Running it

```
export GEMINI_API_KEY=...            # the only provider exercised in the committed runs
python -m ledeline.evals.runner \
  --models gemini:gemini-2.5-flash-lite gemini:gemini-2.5-flash \
  --baseline gemini:gemini-2.5-flash-lite \
  --judge gemini:gemini-2.5-flash \
  --out results/run.json
python -m ledeline.report results/run.json site/index.html
```

No dependencies beyond the Python 3.11+ standard library. Swapping a model is a change to the
`--models` list, and a new model has to pass the same gate as the last one.

## Ship gate semantics

A candidate config ships against the baseline only if:

1. on every story, it fails **no deterministic check the baseline passed** (a new ungrounded
   number on one story blocks the ship, whatever the averages say), and
2. its mean judge score does not fall by more than the tolerance (default 0.5 of 8).

"Better on average" is the wrong question when the failure mode is inventing a number.

## Honest limits

- Only the Gemini adapter has been run here (free tier). The Anthropic and OpenAI adapters follow
  the public REST shapes and say in their docstrings that they are unverified in this repo.
- The judge is a Gemini model grading Gemini outputs. It is a different model from the candidate
  in the committed run, but it is still the same vendor; a second-vendor judge is the obvious
  next step and is a one-line config change.
- The golden notes are one person's editorial judgment written in an evening.
- Ten stories is a smoke corpus. The runner takes any number.
