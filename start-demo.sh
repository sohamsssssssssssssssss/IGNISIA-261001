#!/bin/bash
# One-command demo startup — no Docker, no Redis, no MinIO required.
# Usage: ./start-demo.sh

set -e

export DEMO_MODE=true

echo "============================================"
echo "  IntelliCredit — Demo Mode"
echo "  All agents using cached fixture data"
echo "============================================"
echo ""

# Start backend
echo "[1/2] Starting FastAPI backend on :8000..."
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload &
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
