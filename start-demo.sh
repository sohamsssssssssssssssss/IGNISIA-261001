#!/bin/bash
# One-command demo startup — no Docker, no Redis, no MinIO required.
# Usage: ./start-demo.sh

set -e

export DEMO_MODE=true

has_ml_runtime() {
  local candidate="$1"
  "$candidate" - <<'PY' >/dev/null 2>&1
import importlib.util
required = ("xgboost", "sklearn", "shap", "mlxtend")
raise SystemExit(0 if all(importlib.util.find_spec(name) for name in required) else 1)
PY
}

has_native_chroma() {
  local candidate="$1"
  "$candidate" - <<'PY' >/dev/null 2>&1
try:
    import chromadb
    from chromadb.config import Settings
    chromadb.PersistentClient(path="/tmp/intellicredit_chroma_probe", settings=Settings(anonymized_telemetry=False))
except Exception:
    raise SystemExit(1)
raise SystemExit(0)
PY
}

BACKEND_PYTHON="python"
FULL_BACKEND_PYTHON=""
for candidate in "$(pwd)/backend/.venv/bin/python" "$(pwd)/backend/venv/bin/python"; do
  if [ -x "$candidate" ] && has_ml_runtime "$candidate"; then
    if has_native_chroma "$candidate"; then
      FULL_BACKEND_PYTHON="$candidate"
      break
    fi
    if [ "$BACKEND_PYTHON" = "python" ]; then
      BACKEND_PYTHON="$candidate"
    fi
  fi
done

if [ -n "$FULL_BACKEND_PYTHON" ]; then
  BACKEND_PYTHON="$FULL_BACKEND_PYTHON"
fi

if [ "$BACKEND_PYTHON" = "python" ]; then
  echo "Warning: no local backend virtualenv with xgboost/sklearn/shap was found."
  echo "The backend may fall back to heuristic scoring."
elif [ "$BACKEND_PYTHON" = "$(pwd)/backend/venv/bin/python" ]; then
  echo "Warning: using ML-capable backend env without native Chroma support."
  echo "RAG will run with the in-memory vector fallback."
fi

echo "============================================"
echo "  IntelliCredit — Demo Mode"
echo "  All agents using cached fixture data"
echo "============================================"
echo ""

# Start backend
echo "[1/2] Starting FastAPI backend on :8000..."
cd backend
MPLCONFIGDIR=/tmp "$BACKEND_PYTHON" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
BACKEND_PID=$!
cd ..

# Start frontend
echo "[2/2] Starting React frontend on :5173..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:5173"
echo "Health:   http://localhost:8000/health"
echo ""
echo "Press Ctrl+C to stop both services."

# Cleanup on exit
trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit" INT TERM
wait
