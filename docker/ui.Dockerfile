# Streamlit dashboard — talks to the API over HTTP only, so it needs none of the
# backend's dependencies (no fastapi, sqlalchemy, psycopg, ...).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN pip install --no-cache-dir "streamlit>=1.37.0" "requests>=2.32.0" "pandas>=2.2.0"

COPY ui ./ui

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8501

# Streamlit's own health endpoint — reports whether the Tornado server (and its
# session/script-run machinery) is actually serving, not just that the process
# started.
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health', timeout=3)" || exit 1

CMD ["streamlit", "run", "ui/app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
