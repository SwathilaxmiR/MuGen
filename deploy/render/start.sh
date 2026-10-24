#!/bin/sh
# Render free tier: no background workers, so the API and one worker share this container.
# Long tracks may exceed the free instance's 512 MB and restart the container (accepted for the free demo).
set -e
python -m musicengine.cli init-bucket || echo "bucket init failed (storage asleep?); the worker retries on first upload"
python -m musicengine.worker.loop &
exec uvicorn musicengine.api.main:app --host 0.0.0.0 --port "${PORT:-8000}"
