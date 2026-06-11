#!/bin/bash
# Øyenstikker startup script

PROJECT="/mnt/d/projects/memory-system"
cd "$PROJECT"
source "$PROJECT/venv/bin/activate"

echo ""
echo "  ── Øyenstikker ──────────────────────────"

# ── Docker / Postgres ─────────────────────────
if docker compose ps --status running 2>/dev/null | grep -q "postgres"; then
  echo "  ✓ postgres already running"
else
  echo "  ▸ starting postgres..."
  docker compose up -d 2>/dev/null
  echo "  ▸ waiting for database..."
  for i in $(seq 1 20); do
    docker exec memory-system-postgres-1 pg_isready -U postgres -q 2>/dev/null && break
    sleep 1
  done
  echo "  ✓ database ready"
fi

# ── Monitoring stack ──────────────────────────
if docker compose -f monitoring/docker-compose.monitoring.yml ps --status running 2>/dev/null | grep -q "grafana"; then
  echo "  ✓ monitoring already running"
else
  echo "  ▸ starting monitoring stack..."
  docker compose -f monitoring/docker-compose.monitoring.yml up -d 2>/dev/null
  echo "  ✓ grafana at http://localhost:3000"
fi

# ── MinIO watcher ─────────────────────────────
if pgrep -f "minio_watcher.py" > /dev/null; then
  echo "  ✓ minio watcher already running (pid $(pgrep -f minio_watcher.py))"
else
  echo "  ▸ starting minio watcher..."
  mkdir -p logs
  python minio_watcher.py >> logs/watcher.log 2>&1 &
  echo "  ✓ watcher running (pid $!), logs at logs/watcher.log"
fi

# ── API ───────────────────────────────────────
if curl -s http://localhost:8000/openapi.json > /dev/null 2>&1; then
  echo "  ✓ API already running at http://localhost:8000"
  echo "  ─────────────────────────────────────────"
  echo ""
  echo "  everything already up — nothing to start"
  echo ""
else
  echo "  ▸ starting API on http://localhost:8000"
  echo "  ─────────────────────────────────────────"
  echo ""
  echo "  ctrl+c to stop API (watcher and monitoring keep running)"
  echo ""
  uvicorn fuse:app --host 0.0.0.0 --port 8000 --reload
fi
