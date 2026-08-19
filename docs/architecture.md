# Architecture

Commerce Intelligence exists to answer three questions: **what should I sell,
where should I buy it, and will it make money?** — the `opportunity`, `suppliers`,
and `profitability` modules below map directly onto those three, in that order.

It's a **modular monolith**: one deployable FastAPI service, organized into
business modules with clear boundaries, plus a Streamlit dashboard that talks to
it over HTTP like any other client. There is no microservice split and no
multi-agent orchestration framework — see [Non-goals](#non-goals-for-the-mvp) for
why, and what would change that later.

## System overview

```
                     ┌──────────────┐
                     │  ui/ (Streamlit)  │  talks to the API only — no DB/module access
                     └────────┬─────┘
                              │ HTTP
                     ┌────────▼─────┐
                     │  app/api/v1  │  routers → services, no business logic
                     └────────┬─────┘
                              │
        ┌─────────────┬──────┴──────┬──────────────┐
        │             │             │              │
  ┌─────▼────┐  ┌─────▼─────┐ ┌─────▼──────┐ ┌──────▼─────┐
  │opportunity│  │ suppliers │ │profitability│ │    runs    │  app/modules/*
  └─────┬────┘  └─────┬─────┘ └─────┬──────┘ └──────┬─────┘
        │             │             │       (orchestrates the above three)
        └─────────────┴──────┬──────┴──────────────┘
                              │
                     ┌────────▼─────┐
                     │ integrations │  interface + provider per external concern
                     └────────┬─────┘
                              │
                     ┌────────▼─────┐
                     │  PostgreSQL  │
                     └──────────────┘
```

## Module boundaries

Every business module in `app/modules/` follows the same internal shape:

| File | Responsibility |
|---|---|
| `models.py` | SQLAlchemy ORM tables |
| `schemas.py` | Pydantic response (and sometimes request) models — the API-facing contract |
| `repository.py` | Plain data access: `select`/`add`/`get`, no business logic |
| `service.py` | The actual logic; owns whether it commits or leaves that to a caller |

| Module | Answers | Owns |
|---|---|---|
| `opportunity` | *What should I sell?* | Turning a search query into ranked `ProductOpportunity` rows. `ranking.py` is pure scoring logic with no I/O. |
| `suppliers` | *Where should I buy it?* | Finding and persisting `Supplier` / `SupplierOffer` rows for a shortlisted opportunity. Deduplicates suppliers by `(name, source)`. |
| `profitability` | *Will it make money?* | The money math. `calculator.py` is dependency-free arithmetic (landed cost, margin, ROI, decision thresholds); `service.py` applies it and writes `ProfitabilityCalculation` + `Recommendation` rows. |
| `runs` | — | The only module allowed to call the other three in sequence. Owns `SearchRun` lifecycle: `start_run()` commits immediately (visible as `PENDING`), `execute_run()` runs the pipeline in one transaction — commits everything on success, rolls back and marks `FAILED` with a reason on any error. |

`app/integrations/*` holds one `interface.py` (a `Protocol`) plus one or more
providers per external concern — search, suppliers, marketplace, AI. Modules
depend on the interface, never a concrete provider; `app/integrations/factory.py`
reads `Settings` and picks the implementation. Every provider ships a deterministic
**mock** implementation, which is what makes the whole pipeline runnable with zero
external API keys.

`app/shared/call_logger.py` centralizes the integration audit trail: any module
that calls a provider logs one `IntegrationCallLog` row through the same function,
rather than each module inventing its own logging.

`app/api/*` is a thin translation layer — HTTP ↔ service calls, no business logic.
If a rule lives in a route handler instead of a module's `service.py`, it's in the
wrong place.

`ui/` enforces the same rule as any other API client: it imports nothing from
`app/`, only `requests` calls through `ui/api_client.py`. The dashboard could be
swapped for a different frontend without touching the backend.

## The pipeline

A search request is a **synchronous** pipeline owned by `runs/service.py`:

1. `start_run()` creates and commits a `SearchRun` (`PENDING`) — visible immediately, before anything slow or fallible runs.
2. `execute_run()` sets `RUNNING`, commits, then:
   - `opportunity.discover_opportunities()` — calls the search provider, scores and ranks candidates.
   - For each of the top 5 ranked opportunities: `suppliers.source_suppliers()` then `profitability.evaluate_profitability()`.
3. On success: `COMPLETE` + `completed_at`, one commit for the whole pipeline's results.
4. On any exception: full rollback (nothing from step 2 persists), `FAILED` + `error_message`, committed. The run itself is *not* lost — only the failed pipeline's partial writes are.

This transactional shape is deliberate: every module's `service.py` says explicitly
in its docstring that it adds rows to the session but does not commit — `runs` is
the only place that decides when a set of writes becomes durable.

## Design decisions worth knowing

- **Rule-based recommendation, not AI-based.** `determine_decision()` is a fixed
  threshold on margin % and ROI % (both must clear it together). This keeps the
  decision predictable and free to run. An AI provider is wired up
  (`app/integrations/ai/`) and can be used to *phrase* the rationale more richly
  later without changing what data drives the decision.
- **Two fee percentages, one stored column.** `Settings.default_marketplace_fee_pct`
  and `default_payment_fee_pct` are configured separately but combined into a
  single `fee_pct` before `calculator.calculate_profitability()` — the
  `ProfitabilityCalculation.assumptions` JSONB column records the breakdown that
  was actually used, so a calculation is still auditable.
- **Landed cost divides shipping across MOQ.** A `SupplierOffer.shipping_cost` is a
  per-shipment quote, not per-unit; `calculator.compute_landed_cost()` spreads it
  across the offer's MOQ on the assumption you order exactly that quantity. Stated
  explicitly in the function's docstring since it's a real simplification.
- **`recalculate()` writes a new row, never mutates one.** The "what-if" endpoint
  keeps the original calculation and recommendation intact, so trying different
  assumptions never loses the numbers a decision was actually based on.
- **Alembic reads its URL from `Settings`, not `alembic.ini`.** `alembic/env.py`
  calls `get_settings().database_url` — there's exactly one place `DATABASE_URL` is
  configured, so a migration can't silently run against the wrong database because
  two config files drifted apart.
- **Test isolation via SAVEPOINT, not a full DB wipe per test.** Application code
  calls `db.commit()` in several places (the orchestrator, `recalculate()`).
  `tests/conftest.py`'s `db_session` fixture uses SQLAlchemy's
  `join_transaction_mode="create_savepoint"` so those real commits still happen,
  while the *outer* transaction — and everything inside it — rolls back after each
  test.

## Non-goals for the MVP

Deliberately out of scope, and why — see the repository's earlier design
conversation for the full list:

- **No async job queue.** A search runs synchronously in-request. Worth revisiting
  once run volume or provider latency makes that too slow — `start_run()` /
  `execute_run()` are already split for exactly that future change.
- **No multi-agent orchestration.** `runs/service.py` is a plain sequential
  function, not an autonomous agent. Nothing here rules it out later; there's just
  no concrete case yet that a fixed sequence can't handle.
- **No auth, multi-tenancy, or billing.** Single-client MVP. The API's versioning
  (`/api/v1`) and the DB schema don't block adding it.
- **No marketplace auto-listing or order management.** This is a decision-support
  tool, not a transacting one — a deliberately different, smaller risk surface.

## Repository layout

```
app/
├── main.py                 FastAPI app factory
├── config.py                Settings (pydantic-settings, .env-driven)
├── logging.py                structlog configuration
├── api/                      routers → services (v1/{health,runs,opportunities}.py);
│                              system.py (/health, /ready); middleware.py (request_id)
├── db/                        Base, session, models_registry (for Alembic)
├── modules/                   opportunity, suppliers, profitability, runs
├── integrations/               search, suppliers, marketplace, ai — interface + mock providers
└── shared/                     ai client/prompts, call_logger, IntegrationCallLog

alembic/                      migrations (env.py reads DATABASE_URL from Settings)
ui/                            Streamlit dashboard — imports nothing from app/
tests/
├── conftest.py                 SAVEPOINT-based db_session + TestClient fixtures
├── unit/                        pure logic, no DB, always runs
└── integration/                  needs Postgres — skips cleanly if unreachable
docker/                       api.Dockerfile, ui.Dockerfile
docker-compose.yml            db + api + ui, one command
```
