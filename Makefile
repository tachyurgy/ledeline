.PHONY: test run report
test:
	python3 -m pytest -q tests
run:
	python3 -m ledeline.evals.runner --models gemini:gemini-2.5-flash-lite gemini:gemini-2.5-flash --baseline gemini:gemini-2.5-flash-lite --judge gemini:gemini-2.5-flash --out results/run.json
report:
	python3 -m ledeline.report results/run-2026-09-15.json site/index.html
