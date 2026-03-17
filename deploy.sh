#!/bin/sh

set -eu

echo "🚀 Deploying Break the Code webapp..."

if [ -f .env ]; then
    set -a
    . ./.env
    set +a
fi

PORT="${PORT:-5000}"
GIT_REMOTE="${GIT_REMOTE:-origin}"
DEPLOY_BRANCH="${DEPLOY_BRANCH:-main}"
SKIP_GIT_PULL="${SKIP_GIT_PULL:-0}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
VENV_DIR="${VENV_DIR:-.venv}"
VENV_PYTHON="${VENV_DIR}/bin/python"
GUNICORN_BIN="${VENV_DIR}/bin/gunicorn"

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "❌ ${PYTHON_BIN} not found on PATH"
    exit 1
fi

# Pull latest changes unless explicitly skipped for local runs.
if [ "${SKIP_GIT_PULL}" = "1" ]; then
    echo "⏭️ Skipping git pull"
else
    git pull "${GIT_REMOTE}" "${DEPLOY_BRANCH}"
fi

# Create or reuse a project-local virtual environment so deploy does not
# depend on system-wide pip/gunicorn commands being installed.
if [ ! -d "${VENV_DIR}" ]; then
    echo "📦 Creating virtual environment in ${VENV_DIR}..."
    "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

echo "📦 Installing dependencies..."
"${VENV_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1 || true
"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install -r requirements.txt

if [ ! -x "${GUNICORN_BIN}" ]; then
    echo "❌ gunicorn was not installed into ${VENV_DIR}"
    exit 1
fi

# Stop only this user's matching gunicorn processes.
if command -v pgrep >/dev/null 2>&1; then
    EXISTING_PIDS="$(pgrep -u "$(id -u)" -f "gunicorn.*app:app" || true)"
    if [ -n "${EXISTING_PIDS}" ]; then
        echo "🛑 Stopping existing gunicorn processes: ${EXISTING_PIDS}"
        for pid in ${EXISTING_PIDS}; do
            kill "${pid}" || true
        done
    fi
else
    echo "⚠️ pgrep not found; skipping old-process cleanup"
fi

echo "🚀 Starting gunicorn on port ${PORT}..."
nohup "${GUNICORN_BIN}" --worker-class gevent -w 1 --bind "0.0.0.0:${PORT}" app:app > app.log 2>&1 &
APP_PID=$!

sleep 2
if ! kill -0 "${APP_PID}" 2>/dev/null; then
    echo "❌ Gunicorn failed to start. Check app.log for details."
    exit 1
fi

echo "✅ Deployment complete! App running on port ${PORT} (pid ${APP_PID})"
