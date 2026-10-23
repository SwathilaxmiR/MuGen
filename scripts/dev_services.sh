#!/usr/bin/env bash
# Run postgres + minio natively when Docker is not available (dev convenience only).
# Needs `postgres`, `initdb`, `pg_ctl` and `minio` on PATH (e.g. from conda-forge).
set -euo pipefail
DIR="${DEV_DATA_DIR:-$(pwd)/.local}"
mkdir -p "$DIR"
case "${1:-start}" in
  start)
    if [ ! -d "$DIR/pg" ]; then
      initdb -D "$DIR/pg" -U music --auth=trust >/dev/null
    fi
    pg_ctl -D "$DIR/pg" -l "$DIR/pg.log" -o "-p 5432 -k $DIR" start >/dev/null
    sleep 1
    createdb -h localhost -U music music 2>/dev/null || true
    MINIO_ROOT_USER=minioadmin MINIO_ROOT_PASSWORD=minioadmin \
      nohup minio server "$DIR/minio" --address :9000 --console-address :9001 >"$DIR/minio.log" 2>&1 &
    echo $! >"$DIR/minio.pid"
    echo "postgres :5432, minio :9000 started (data in $DIR)"
    ;;
  stop)
    pg_ctl -D "$DIR/pg" stop >/dev/null || true
    [ -f "$DIR/minio.pid" ] && kill "$(cat "$DIR/minio.pid")" 2>/dev/null || true
    rm -f "$DIR/minio.pid"
    echo stopped
    ;;
esac
