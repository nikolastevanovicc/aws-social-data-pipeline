FROM apache/superset:latest

USER root

RUN set -eux; \
    if [ -x /app/.venv/bin/python ]; then \
        PYTHON=/app/.venv/bin/python; \
    else \
        PYTHON="$(command -v python3 || command -v python)"; \
    fi; \
    "$PYTHON" -m ensurepip --upgrade || true; \
    "$PYTHON" -m pip install --no-cache-dir --upgrade pip; \
    "$PYTHON" -m pip install --no-cache-dir psycopg2-binary; \
    "$PYTHON" -c "import psycopg2"

USER superset
