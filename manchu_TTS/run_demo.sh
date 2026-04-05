#!/usr/bin/env bash
set -euo pipefail

# Run from repo root: bash manchu_TTS/run_demo.sh
cd "$(dirname "$0")/.."

PORT="${MANCHU_TTS_PORT:-7868}"

echo "[manchu_TTS] Starting demo server..."
echo "[manchu_TTS] Project root: $PWD"
echo "[manchu_TTS] Listen port: ${PORT}"

PYTHON_PATH="$(command -v python || true)"
echo "[manchu_TTS] Current python: ${PYTHON_PATH:-not-found}"

if [[ "${CONDA_DEFAULT_ENV:-}" == "GPTSoVits" ]] && [[ "${PYTHON_PATH}" == *"/envs/GPTSoVits/"* ]]; then
	echo "[manchu_TTS] Using active conda env: GPTSoVits"
	echo "[manchu_TTS] Open: http://127.0.0.1:${PORT}"
	exec python -m uvicorn manchu_TTS.app:app --host 0.0.0.0 --port "${PORT}" --log-level info
fi

echo "[manchu_TTS] Active env/python is not GPTSoVits, switching via conda run"
echo "[manchu_TTS] Open: http://127.0.0.1:${PORT}"
exec conda run -n GPTSoVits python -m uvicorn manchu_TTS.app:app --host 0.0.0.0 --port "${PORT}" --log-level info
