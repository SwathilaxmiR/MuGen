.PHONY: up down test test-local batch openapi logs

up:
	GIT_SHA=$$(git rev-parse HEAD) docker compose up -d --build --wait api worker

down:
	docker compose down

# whole suite (unit + integration + e2e) inside compose, no API keys
test:
	mkdir -p out
	docker compose --profile tests run --rm --build tests

# unit tests only on the host (needs .venv); integration/e2e skip without services
test-local:
	.venv/bin/pytest -q -rs

batch:
	mkdir -p out
	docker compose --profile tests run --rm tests \
	  python -m musicengine.cli batch --api http://api:8000 --token "$${API_TOKEN}" --input tests/inputs --out out/

openapi:
	.venv/bin/python -m musicengine.cli export-openapi openapi.yaml

logs:
	docker compose logs -f api worker

# ---- submission evidence (see EVIDENCE_AND_FORM_PLAN / FORM_REPORT.md). Local stack must be running on :8000.
EVPY = .venv/bin/python
evidence-runs:
	$(EVPY) evidence/tools/run_matrix.py --api http://localhost:8000 --local-control --run-id $${RUN_ID:-$$(date +%Y%m%d-%H%M)}

evidence-verify:
	cd evidence/verify && ../../$(EVPY) must_haves.py && ../../$(EVPY) levels.py && ../../$(EVPY) hard_cases.py \
	  && ../../$(EVPY) integration.py && ../../$(EVPY) listening.py

evidence-metrics:
	cd evidence/verify && ../../$(EVPY) metrics.py --load

evidence-eval:
	cd evidence/verify && ../../$(EVPY) eval_quality.py

evidence-form:
	cd evidence/verify && ../../$(EVPY) summary.py && ../../$(EVPY) consistency.py
	$(EVPY) scripts/fill_form.py

audio-pack:
	cd out/evidence/$$(cat evidence/runs/LATEST) && zip -qr ../../../audio-pack.zip . -x '*.tmp.wav'

evidence: evidence-runs evidence-verify evidence-metrics evidence-eval evidence-form audio-pack
