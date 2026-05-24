#!/bin/sh
# Demo deploy entrypoint (Fly.io combined-container).
#
# 1. Start uvicorn in the background.
# 2. Wait for /health to return 200 (lifespan create_all has run).
# 3. Run seed.py — idempotent; skips broker registration on 409 (already exists).
# 4. Wait on uvicorn so the container stays alive + Fly sees the process.
#
# seed.py only runs ONCE on first boot since broker registration is idempotent
# and add_client checks for duplicates. Re-runs across deploys cost ~2s and
# don't mutate anything.

set -eu

echo "[entrypoint] starting uvicorn on 0.0.0.0:8000"
uvicorn healthflow.main:app --host 0.0.0.0 --port 8000 &
UVICORN_PID=$!

echo "[entrypoint] waiting for /health"
i=0
while [ "$i" -lt 30 ]; do
    if python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=1)" 2>/dev/null; then
        echo "[entrypoint] backend healthy after ${i}s"
        break
    fi
    i=$((i + 1))
    sleep 1
done

if [ "$i" -ge 30 ]; then
    echo "[entrypoint] backend never became healthy — exiting"
    kill "$UVICORN_PID" 2>/dev/null || true
    exit 1
fi

echo "[entrypoint] seeding demo data (idempotent)"
python seed.py || echo "[entrypoint] seed.py exited non-zero — broker probably already exists; continuing"

echo "[entrypoint] handing off to uvicorn (pid=$UVICORN_PID)"
wait "$UVICORN_PID"
