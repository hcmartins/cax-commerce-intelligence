# Backend API — FastAPI app + Alembic migrations, no UI dependencies.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN pip install --no-cache-dir .

# Runs as an unprivileged user rather than the image's default root, and owns
# only what it needs under /app.
RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

# Mirrors docker-compose.yml's api healthcheck, so `docker run` on this image
# standalone (outside compose) still reports health. Checks readiness (DB
# reachable), not just liveness — a container marked "healthy" here is one
# that's actually safe to route traffic to.
HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/ready', timeout=3)" || exit 1

# Migrations run every start: cheap and idempotent when already at head, and it
# means "docker compose up" alone is enough to get a schema — no separate manual
# migration step for whoever is running this. `exec` replaces the shell with
# uvicorn (instead of leaving it as a child process), so uvicorn receives
# SIGTERM directly on `docker stop` and shuts down gracefully instead of being
# killed after the shell fails to forward the signal.
# WEB_CONCURRENCY controls uvicorn's worker count (default 1 — safe for the
# MVP's synchronous, single-container deployment; raise it once request volume
# warrants more than one process).
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-1}"]
