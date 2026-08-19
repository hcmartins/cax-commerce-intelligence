# Commerce Intelligence

Answers three questions for a buying-and-selling business: **what should I sell,
where should I buy it, and will it make money?**

Given a search, it discovers potentially profitable products (*what to sell*),
sources suppliers for them globally (*where to buy*), calculates landed-cost
profitability, and returns a **BUY/TEST**, **WATCH**, or **REJECT** call (*will it
make money*) — with every run, opportunity, supplier, calculation, and
recommendation persisted for later review.

Runs end-to-end with **zero external API keys**: every integration (search,
suppliers, marketplace, AI) ships a deterministic mock provider, so the full
pipeline is demoable on day one. Swap in a real provider later by implementing its
interface and pointing the matching `*_PROVIDER` env var at it — nothing else
changes.

See [`docs/architecture.md`](docs/architecture.md) for how it's put together and
why, and [`docs/api.md`](docs/api.md) for the full API reference.

## Environments at a glance

The same image (`docker/api.Dockerfile`) and the same `.env`-driven `Settings`
(`app/config.py`) run everywhere — only the environment variables and what's
standing behind them change.

| | Local | DEV (Azure) | PROD (Azure) |
|---|---|---|---|
| How | `docker compose up --build` | Azure Container Apps | Azure Container Apps |
| Database | Postgres container | Azure PostgreSQL Flexible Server (public, Azure-services-only firewall) | Azure PostgreSQL Flexible Server (private/VNet) |
| Secrets | `.env` file (gitignored) | Azure Key Vault, read via managed identity | Azure Key Vault, read via managed identity |
| Image | built locally | Azure Container Registry | Azure Container Registry (promoted DEV image, not a fresh build) |
| Replicas | 1 (single container) | min 1 / max 3 | higher min, autoscale rules |
| Logs | console (or JSON with `LOG_JSON=true`) | JSON → Log Analytics / App Insights | JSON → Log Analytics / App Insights |
| Status | — | see [Deploying to Azure (DEV)](#deploying-to-azure-dev) | **not yet provisioned** — see [Deploying to Azure (PROD)](#deploying-to-azure-prod) |

## Quickstart (Docker Compose)

One command brings up the whole stack — Postgres, the API (migrations run
automatically on container start), and the dashboard:

```bash
cp .env.example .env
docker compose up --build
```

- **Dashboard:** http://localhost:8501
- **API:** http://localhost:8000/api/v1 — interactive docs at
  [`/docs`](http://localhost:8000/docs) (Swagger UI) and
  [`/redoc`](http://localhost:8000/redoc), raw schema at
  [`/openapi.json`](http://localhost:8000/openapi.json)
- **Health:** [`/health`](http://localhost:8000/health) (liveness) and
  [`/ready`](http://localhost:8000/ready) (readiness — DB included)

Wait for `docker compose ps` to show the `api` and `ui` containers as
`healthy` (both images ship a `HEALTHCHECK`) before treating the stack as up —
`ui` won't even start serving until `api` reports healthy.

If a port is already taken on your machine (e.g. a native Postgres already on
5432), override it in `.env` before starting — see `POSTGRES_HOST_PORT`,
`API_HOST_PORT`, `UI_HOST_PORT`.

To stop:

```bash
docker compose down        # keep the database volume
docker compose down -v     # also delete it
```

## Docker build (API image only)

To build/inspect the API image on its own, without the rest of the stack:

```bash
docker build -f docker/api.Dockerfile -t commerce-intelligence-api .
docker run --rm -p 8000:8000 --env-file .env \
  -e DATABASE_URL="postgresql+psycopg://ai_commerce:ai_commerce@host.docker.internal:5432/ai_commerce" \
  commerce-intelligence-api
```

(`host.docker.internal` reaches a Postgres running on your host machine from
inside the container; point it at any reachable Postgres instead if you have
one elsewhere.) The same pattern builds the dashboard image:

```bash
docker build -f docker/ui.Dockerfile -t commerce-intelligence-ui .
```

## Local development (without Docker)

Requires Python 3.11+ and a running Postgres.

```bash
cp .env.example .env               # edit DATABASE_URL if not using the defaults
pip install -e ".[dev,ui]"

alembic upgrade head               # create the schema
uvicorn app.main:app --reload      # API on :8000

# in another terminal
streamlit run ui/app.py            # dashboard on :8501
```

Then verify the API's up: `curl http://localhost:8000/health` and
`curl http://localhost:8000/ready`.

## Tests

Three layers, all under `pytest`/`tests/`:

| Layer | Location | Needs | Runs by default? |
|---|---|---|---|
| Unit | `tests/unit/` | nothing | yes |
| Integration (API + modules) | `tests/integration/` | a Postgres **test** database | yes — skips cleanly if unreachable |
| Smoke | `tests/smoke/` | a running deployment (e.g. `docker compose up`) | yes — skips cleanly if unreachable |

```bash
pytest                             # everything; integration/smoke skip cleanly
                                    # if their dependency isn't reachable
pytest -m "not integration and not smoke"   # unit tests only, no DB/server needed
```

Integration tests need a **dedicated test database** (never point this at your dev
database — the suite creates and drops the whole schema):

```bash
docker run -d --name commerce-intelligence-test-db -p 5432:5432 \
  -e POSTGRES_USER=ai_commerce -e POSTGRES_PASSWORD=ai_commerce \
  -e POSTGRES_DB=ai_commerce_test postgres:16-alpine

pytest   # or: TEST_DATABASE_URL=... pytest, if 5432 is already taken locally
```

## Smoke testing

`tests/smoke/` exercises a **running** deployment over real HTTP — liveness,
readiness, OpenAPI/Swagger being served, the `X-Request-ID` correlation header,
and the full discovery → sourcing → profitability pipeline end to end. Run it
against the Compose stack once it's up:

```bash
docker compose up --build -d
pytest -m smoke                                  # defaults to http://localhost:8000
SMOKE_BASE_URL=https://staging.example.com pytest -m smoke   # or any other deployment
```

## Database migrations

```bash
alembic revision --autogenerate -m "describe the change"   # after editing a model
alembic upgrade head
alembic downgrade -1                                        # roll back one step
```

`alembic/env.py` reads `DATABASE_URL` from the app's own `Settings` — there's no
separate connection string to keep in sync inside `alembic.ini`.

## Project layout

```
app/            FastAPI backend — config, db, api/, modules/, integrations/, shared/
alembic/        migrations
ui/             Streamlit dashboard (talks to the API only)
tests/          unit/ (no DB), integration/ (needs Postgres), smoke/ (needs a
                running deployment) — the latter two skip cleanly if absent
docker/         Dockerfiles for the api and ui images
docker-compose.yml
infra/          Bicep templates for Azure (base.bicep + app.bicep, each with parameters) + GitHub OIDC setup script
.github/        CI/CD workflow (ci-cd.yml): test on every push/PR, build+push+deploy on push to main
docs/           architecture.md, api.md
```

Full breakdown in [`docs/architecture.md`](docs/architecture.md).

## Configuration

All settings are environment variables, documented in [`.env.example`](.env.example)
— copy it to `.env` and adjust. Nothing needs a real value to run: every provider
defaults to `mock`. **Never commit `.env`** (already in `.gitignore`) — it's
where real keys (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, etc.) belong if you set
any; `.env.example` only ever ships empty placeholders.

## Logging & correlation IDs

Structured logging via `structlog` (`app/logging.py`) — set `LOG_JSON=true` for
JSON output (production/log-aggregator friendly) or leave `false` for a
human-readable console format (local dev). Every request gets an `X-Request-ID`
(generated, or echoed back if the caller sent one) that's attached to every log
line emitted while handling it; `POST /runs` additionally binds `run_id` for the
whole pipeline, so one run's logs — across discovery, sourcing, and
profitability — can be filtered by a single field. See
[`app/api/middleware.py`](app/api/middleware.py).

## Deploying to Azure (DEV)

Same image, same app — deployed onto Azure Container Apps instead of Compose.
No application code changes; only environment variables and where secrets come
from differ. Infrastructure is defined in two Bicep templates — that's the
source of truth; what follows is the narrative summary:

- [`infra/base.bicep`](infra/base.bicep) — everything except the app itself
  (registry, database, vault, identity, logging). Deploy once; redeploy only
  when infra changes.
- [`infra/app.bicep`](infra/app.bicep) — the Container App. Deploy every time
  a new image is pushed.

They're split because the Container App needs an image to already exist in
the registry `base.bicep` creates — one combined template can't bootstrap
both on a first-ever deploy.

**Resources** (all in one resource group, one region):

| Resource | Purpose |
|---|---|
| Azure Container Registry (Basic) | holds the built image |
| Azure Container Apps Environment (Consumption) | hosts the app |
| Azure Container App | runs `docker/api.Dockerfile`'s image |
| Azure Database for PostgreSQL Flexible Server (Burstable B1ms) | the app's database |
| Azure Key Vault (RBAC-authorized) | holds `database-url` — nothing else is secret |
| User-assigned managed identity | `AcrPull` on the registry, `Key Vault Secrets User` on the vault — this is how the Container App authenticates to both, with **no stored credentials anywhere** |
| Log Analytics workspace + Application Insights | the Container Apps environment ships stdout/stderr here automatically (`ContainerAppConsoleLogs_CL`) — since the app already logs structured JSON (`LOG_JSON=true`), those logs land pre-structured, no extra app-side instrumentation needed |

**Deploy:**

```bash
az login
RG=rg-commerce   # must already exist
az provider register -n Microsoft.App
az provider register -n Microsoft.OperationalInsights
az provider register -n Microsoft.Insights
az provider register -n Microsoft.ContainerRegistry
az provider register -n Microsoft.DBforPostgreSQL
az provider register -n Microsoft.KeyVault

# 1. Infra — registry, database, vault, identity, logging. Once; re-run only
#    when infra itself changes.
az deployment group create -g $RG -f infra/base.bicep \
  -p infra/base.parameters.dev.json \
  postgresAdminPassword='<generate-a-strong-password-do-not-commit-it>'

# 2. Build and push the image, now that the registry exists.
docker build -f docker/api.Dockerfile -t commerce-intelligence-api:0.1.0 .
ACR=$(az deployment group show -g $RG -n base --query properties.outputs.acrLoginServer.value -o tsv)
az acr login --name "${ACR%%.*}"
docker tag commerce-intelligence-api:0.1.0 $ACR/commerce-intelligence-api:0.1.0
docker push $ACR/commerce-intelligence-api:0.1.0

# 3. The app — every time a new image is pushed, re-run just this one.
az deployment group create -g $RG -f infra/app.bicep -p infra/app.parameters.dev.json
```

Migrations run automatically — the image's `CMD` is `alembic upgrade head &&
exec uvicorn ...`, exactly as in Compose, so there's no separate migration
step to run against Azure Postgres.

**Verify:**

```bash
FQDN=$(az deployment group show -g $RG -n app --query properties.outputs.containerAppFqdn.value -o tsv)
curl "https://$FQDN/health" && curl "https://$FQDN/ready"
SMOKE_BASE_URL="https://$FQDN" pytest -m smoke
```

Structured logs are queryable in Log Analytics immediately:

```bash
WORKSPACE=$(az deployment group show -g $RG -n base --query properties.outputs.logAnalyticsWorkspaceName.value -o tsv)
CUSTOMER_ID=$(az monitor log-analytics workspace show -g $RG -n $WORKSPACE --query customerId -o tsv)
az monitor log-analytics query --workspace $CUSTOMER_ID --analytics-query \
  "ContainerAppConsoleLogs_CL | order by TimeGenerated desc | take 20"
```

One config step both templates deliberately leave out — its ARM schema is
still preview/evolving, so it's a manual post-deploy command instead of
something pinned in Bicep:

```bash
CONN_STRING=$(az deployment group show -g $RG -n base --query properties.outputs.appInsightsConnectionString.value -o tsv)
CAE=$(az deployment group show -g $RG -n base --query properties.outputs.containerAppEnvName.value -o tsv)
az containerapp env telemetry app-insights set -g $RG -n $CAE --connection-string $CONN_STRING
```

**Tear down** the app/environment without touching Postgres or Key Vault:

```bash
CAN=$(az deployment group show -g $RG -n app --query properties.outputs.containerAppName.value -o tsv)
CAE=$(az deployment group show -g $RG -n base --query properties.outputs.containerAppEnvName.value -o tsv)
az containerapp delete -g $RG -n $CAN --yes
az containerapp env delete -g $RG -n $CAE --yes
```

Since everything's defined in the templates, standing it back up later is
just re-running the two `az deployment group create` commands above — no
need to reconstruct anything by hand.

## CI/CD

[`.github/workflows/ci-cd.yml`](.github/workflows/ci-cd.yml): on every push/PR
it runs `ruff` + `pytest` (unit + integration, against a Postgres service
container); on push to `main`, it additionally builds the image, tags it
`<app-version>-<short-sha>`, pushes to ACR, and deploys — to DEV
automatically, to PROD only after a required reviewer approves (a GitHub
Environment protection rule on `production`, not something the workflow file
itself can create — that's a manual step in this repo's own Settings).

**One-time setup**, once this repo exists on GitHub:

```bash
GITHUB_OWNER=<org-or-user> GITHUB_REPO=<repo-name> \
RESOURCE_GROUP=rg-commerce ACR_NAME=acrcommerceintel1dc549 \
./infra/setup-github-oidc.sh
```

This creates an Azure AD app registration trusted via OIDC federated
credentials (no client secret stored anywhere) with `AcrPush` on the registry
and `Contributor` on the resource group, and prints the exact GitHub repo
secrets/variables to set from its output. Then, in the repo's Settings:

- **Environments** → create `dev` (no protection rules) and `production`
  (add required reviewers — this is the manual-approval gate).
- Leave the `PROD_AZURE_RESOURCE_GROUP` variable unset until PROD
  infrastructure actually exists; `deploy-prod` skips cleanly without it
  rather than failing.

## Deploying to Azure (PROD)

*Not yet provisioned.* This is the intended pattern once a PROD environment is
needed, built on the same image and the same `Settings` — only infrastructure
and config differ from DEV, never application code:

- **Separate resource group** (e.g. `rg-commerce-prod`), so DEV changes can
  never affect PROD and the two have independent cost/access boundaries.
- **Private PostgreSQL**: VNet-integrated with no public endpoint, instead of
  DEV's "Azure services only" firewall rule — the Container Apps environment
  would need VNet integration too (a workload profile, not Consumption-only).
- **Key Vault with purge protection** enabled (DEV's does not have it, to
  allow a clean `purge` on teardown).
- **Promoted images, not fresh builds**: PROD pulls the exact image digest
  that was already built, pushed, and smoke-tested in DEV — never rebuilds
  from source — so what's deployed is provably what was tested.
- **Higher `minReplicas`** (no scale-to-zero-adjacent behavior) and autoscale
  rules based on HTTP concurrency, not just a fixed max.
- **CI/CD**, not hand-run `az` commands — build → push → smoke-test-in-DEV →
  promote-to-PROD as pipeline stages, with the smoke suite in `tests/smoke/`
  as the promotion gate.
- **Alerting** on the Application Insights/Log Analytics data already being
  collected (failed readiness probes, 5xx rate, migration failures).

## Remaining risks (PROD and beyond)

- **No app-level distributed tracing.** Application Insights is wired at the
  platform level only (environment → App Insights telemetry link); the app
  itself has no OpenTelemetry/App Insights SDK dependency. Real observability
  today is the structured JSON stdout logs in Log Analytics
  (`request_id`/`run_id`-correlated), not App Insights request/dependency
  traces.
- **DEV Postgres is publicly reachable** (scoped to Azure services, not the
  open internet, but still not VNet-isolated) — acceptable for DEV, not for
  PROD.
# cax-commerce-intelligence
