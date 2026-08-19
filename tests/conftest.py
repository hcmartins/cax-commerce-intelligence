import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db import models_registry  # noqa: F401  (registers every model with Base.metadata)
from app.db.base import Base
from app.db.session import get_db

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://ai_commerce:ai_commerce@localhost:5432/ai_commerce_test",
)

_SKIP_REASON = (
    f"No test database reachable at {TEST_DATABASE_URL}. Start one, e.g.:\n"
    "  docker run -d --name commerce-intelligence-test-db -p 5432:5432 "
    "-e POSTGRES_USER=ai_commerce -e POSTGRES_PASSWORD=ai_commerce "
    "-e POSTGRES_DB=ai_commerce_test postgres:16-alpine\n"
    "...or set TEST_DATABASE_URL to point at one you already have running."
)


@pytest.fixture(scope="session")
def db_engine():
    """One engine per test session, pointed at a dedicated *test* database — never
    the dev database, since this creates and drops the entire schema. Integration
    tests that need this (directly or via `db_session`/`client`) are skipped, not
    failed, when no test database is reachable.
    """

    engine = create_engine(TEST_DATABASE_URL, future=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        pytest.skip(_SKIP_REASON)

    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def db_session(db_engine):
    """A session bound to its own SAVEPOINT, rolled back after every test.

    App code calls `db.commit()` in several places (the run orchestrator commits
    mid-pipeline, `recalculate` commits on its own). `join_transaction_mode=
    "create_savepoint"` lets those real commits happen — releasing the current
    SAVEPOINT and opening a new one — while the outer transaction started here stays
    open until this fixture rolls it back, so nothing a test does ever reaches the
    database beyond this one test.
    """

    connection = db_engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()


@pytest.fixture
def client(db_session):
    """A FastAPI TestClient wired to `db_session`, so API-level tests share the same
    per-test transaction (and rollback) as everything else in the integration suite.
    """

    from app.main import app

    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
