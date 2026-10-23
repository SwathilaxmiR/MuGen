.PHONY: up down test test-local batch openapi logs

up:
	docker compose up -d --build --wait api worker

down:
	docker compose down

# whole suite (unit + integration + e2e) inside compose, no API keys
test:
	docker compose --profile tests run --rm --build tests

# unit tests only on the host (needs .venv); integration/e2e skip without services
test-local:
	.venv/bin/pytest -q -rs

batch:
	docker compose --profile tests run --rm tests \
	  python -m musicengine.cli batch --api http://api:8000 --token "$${API_TOKEN}" --input tests/inputs --out out/

openapi:
	.venv/bin/python -m musicengine.cli export-openapi openapi.yaml

logs:
	docker compose logs -f api worker
