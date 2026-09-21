#!/bin/bash
LISTEN_PORT="${X_ZOHO_CATALYST_LISTEN_PORT:-${PORT:-9000}}"
echo "[start.sh] Starting AGSuite Backend on port ${LISTEN_PORT}..."

# Export PYTHONPATH to include common site-packages locations
export PYTHONPATH=".:/catalyst:/catalyst/.local/lib/python3.12/site-packages:/catalyst/.local/lib/python3/site-packages:/root/.local/lib/python3.12/site-packages:${PYTHONPATH}"

# Find python binary
if [ -f "/catalyst/.venv/bin/python" ]; then
    PYTHON_CMD="/catalyst/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_CMD="python3"
elif command -v python >/dev/null 2>&1; then
    PYTHON_CMD="python"
else
    PYTHON_CMD="python"
fi

echo "[start.sh] Using Python binary: $PYTHON_CMD"

# Check if Django is accessible
if ! $PYTHON_CMD -c "import django" >/dev/null 2>&1; then
    echo "[start.sh] Django not found in environment. Installing requirements..."
    $PYTHON_CMD -m pip install --no-cache-dir --user -r requirements.txt
fi

echo "[start.sh] Launching Django server on 0.0.0.0:$LISTEN_PORT..."
exec $PYTHON_CMD manage.py runserver 0.0.0.0:$LISTEN_PORT


