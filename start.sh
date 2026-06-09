#!/bin/bash
# Øyenstikker startup script

PROJECT="/mnt/d/Projects/memory-system"
cd "$PROJECT"

# Activate venv
source "$PROJECT/venv/bin/activate"

echo ""
echo "  ── Øyenstikker ──────────────────────────"

# Start Docker / postgres
echo "  ▸ starting postgres..."
docker-compose up -d 2>/dev/null

# Wait for postgres to be ready
echo "  ▸ waiting for database..."
for i in $(seq 1 20); do
  docker exec memory-system-postgres-1 pg_isready -U postgres -q 2>/dev/null && break
  sleep 1
done

echo "  ▸ database ready"
echo "  ▸ starting API on http://localhost:8000"
echo "  ▸ ctrl+c to stop"
echo "  ─────────────────────────────────────────"
echo ""

# Start uvicorn (foreground so you see logs and can ctrl+c)
uvicorn fuse:app --host 0.0.0.0 --port 8000 --reload
